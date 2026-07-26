"""Feasibility spike: halfvec hnsw index for aia_chunks.embedding (2560-dim).

Proves on the REAL dev DB (133k chunks): build time, that a FILTERED workspace
query actually uses the index, recall vs exact full-scan, and the speedup. Builds
a PARTIAL index (predicate vector_dims=2560) so a future different-dim model does
not break inserts. Safe to re-run; DROPs nothing unless --drop is passed.
"""
import sys
import time

from src import database as db
from src.services.aia_embeddings import get_embedding_provider
from src.core.db.pool import get_connection

DIM = 2560
IDX = "idx_chunks_embedding_hnsw"
WS_UUID = "1ea7b2fa-b237-4bbd-801b-c9793d388984"
for _a in sys.argv[1:]:
    if _a.startswith("--ws="):
        WS_UUID = _a.split("=", 1)[1]


def q(cur, sql, params=None):
    cur.execute(sql, params or [])
    return cur.fetchall()


def main():
    if "--drop" in sys.argv:
        with get_connection() as c:
            with c.cursor() as cur:
                cur.execute(f"DROP INDEX IF EXISTS {IDX}")
            c.commit()
        print(f"dropped {IDX}")
        return

    # 0) partial-index safety: does a wrong-dim row break the index expression?
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("CREATE TEMP TABLE _t (id int, e vector) ON COMMIT DROP")
            cur.execute("INSERT INTO _t VALUES (1, %s::vector)", ["[" + ",".join(["0.1"] * DIM) + "]"])
            cur.execute("INSERT INTO _t VALUES (2, %s::vector)", ["[0.1,0.2,0.3]"])  # 3-dim
            cur.execute(
                f"CREATE INDEX ON _t USING hnsw ((e::halfvec({DIM})) halfvec_cosine_ops) "
                f"WHERE vector_dims(e) = {DIM}"
            )
            # if we got here, the 3-dim row did NOT break the partial index build
            print("[safety] partial index skips wrong-dim rows: OK (3-dim row did not error)")
        c.rollback()

    # 1) build the real index, timed, with raised maintenance_work_mem
    with get_connection() as c:
        c.autocommit = True
        with c.cursor() as cur:
            # Parallel index build shares work via DSM in /dev/shm, which is only 64MB in a
            # default Docker container -> "could not resize shared memory segment". Disable
            # parallel maintenance so the build uses backend-local maintenance_work_mem instead.
            # PROD NOTE: same /dev/shm limit applies, so the real build must do the same (or the
            # container needs a bigger --shm-size).
            cur.execute("SET max_parallel_maintenance_workers = 0")
            cur.execute("SET maintenance_work_mem = '512MB'")
            exists = q(cur, "SELECT 1 FROM pg_indexes WHERE indexname=%s", [IDX])
            if exists:
                print(f"[build] {IDX} already exists, skipping build")
            else:
                cnt = q(cur, f"SELECT count(*) FROM aia_chunks WHERE vector_dims(embedding)={DIM}")[0][0]
                print(f"[build] building hnsw on {cnt} rows (dim {DIM})...")
                t0 = time.perf_counter()
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS {IDX} ON aia_chunks "
                    f"USING hnsw ((embedding::halfvec({DIM})) halfvec_cosine_ops) "
                    f"WHERE vector_dims(embedding) = {DIM}"
                )
                print(f"[build] done in {time.perf_counter() - t0:.1f}s")
            sz = q(cur, "SELECT pg_size_pretty(pg_relation_size(%s))", [IDX])[0][0]
            print(f"[build] index size: {sz}")

    # 2) prep: workspace + probes (embed 30 real chunk texts)
    ws = db.get_aia_workspace(WS_UUID)
    ws_id = ws["id"]
    source_ids = [s["id"] for s in db.get_aia_sources_by_workspace(ws_id)]
    texts = []
    for sid in source_ids:
        for ch in db.get_aia_chunks_by_source(sid):
            t = (ch.get("content") or "").strip().replace("\n", " ")
            if len(t) > 40:
                texts.append(t[:180])
            if len(texts) >= 30:
                break
        if len(texts) >= 30:
            break
    probes = get_embedding_provider().embed(texts)
    print(f"\n[query] workspace id={ws_id}, {len(source_ids)} sources, {len(probes)} probes")

    def exact_topk(cur, probe):
        # full precision, no usable index -> seqscan = ground truth
        cur.execute(
            """SELECT c.id FROM aia_chunks c JOIN aia_sources s ON s.id=c.source_id
               WHERE s.workspace_id=%s AND s.id=ANY(%s) AND c.embedding IS NOT NULL
               ORDER BY c.embedding <=> %s::vector LIMIT 10""",
            [ws_id, source_ids, str(probe)],
        )
        return [r[0] for r in cur.fetchall()]

    def index_topk(cur, probe):
        cur.execute(
            f"""SELECT c.id FROM aia_chunks c JOIN aia_sources s ON s.id=c.source_id
                WHERE s.workspace_id=%s AND s.id=ANY(%s) AND vector_dims(c.embedding)={DIM}
                ORDER BY c.embedding::halfvec({DIM}) <=> %s::halfvec({DIM}) LIMIT 10""",
            [ws_id, source_ids, str(probe)],
        )
        return [r[0] for r in cur.fetchall()]

    # 3) EXPLAIN: is the index actually used for the filtered query?
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("SET hnsw.iterative_scan = relaxed_order")
            cur.execute("SET hnsw.ef_search = 100")
            cur.execute(
                f"""EXPLAIN (ANALYZE, BUFFERS) SELECT c.id FROM aia_chunks c
                    JOIN aia_sources s ON s.id=c.source_id
                    WHERE s.workspace_id=%s AND s.id=ANY(%s) AND vector_dims(c.embedding)={DIM}
                    ORDER BY c.embedding::halfvec({DIM}) <=> %s::halfvec({DIM}) LIMIT 10""",
                [ws_id, source_ids, str(probes[0])],
            )
            plan = "\n".join(r[0] for r in cur.fetchall())
            used = IDX in plan or "Index Scan using idx_chunks_embedding_hnsw" in plan
            print(f"\n[explain] index used by filtered query: {used}")
            for line in plan.splitlines():
                if any(k in line for k in ("hnsw", IDX, "Seq Scan", "Index Scan", "Execution Time", "actual")):
                    print("   ", line.strip()[:110])

    # 4) recall + speed: exact (seqscan) vs index, same probes
    top1_match = topk_overlap = 0
    t_exact = t_index = 0.0
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("SET hnsw.iterative_scan = relaxed_order")
            cur.execute("SET hnsw.ef_search = 100")
            for p in probes:
                t0 = time.perf_counter(); ex = exact_topk(cur, p); t_exact += time.perf_counter() - t0
                t0 = time.perf_counter(); ix = index_topk(cur, p); t_index += time.perf_counter() - t0
                if ex and ix and ex[0] == ix[0]:
                    top1_match += 1
                if ex:
                    topk_overlap += len(set(ex) & set(ix)) / len(ex)
    n = len(probes)
    print(f"\n[recall] top-1 identical to exact : {top1_match}/{n}")
    print(f"[recall] mean top-10 overlap      : {topk_overlap / n * 100:.0f}%")
    print(f"[speed]  exact seqscan  : {t_exact / n * 1000:.0f} ms/query")
    print(f"[speed]  halfvec index  : {t_index / n * 1000:.0f} ms/query")
    print(f"[speed]  speedup        : {t_exact / t_index:.1f}x")


if __name__ == "__main__":
    main()
