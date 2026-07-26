"""End-to-end A/B of the chip pre-search (the actual chip pause) with vs without the
hnsw index, on identical input. Runs the real production path: _parallel_search over
the same fixed lines calling the real db.hybrid_search_chunks (vector+keyword+substring).
Drops the index, measures, rebuilds it, measures again — so both sides see the same lines.
"""
import time

from src import database as db
from src.services.aia_embeddings import get_embedding_provider
from src.core.db.pool import get_connection
from src.features.ai_assistant.routes._helpers import _parallel_search

IDX = "idx_chunks_embedding_hnsw"
WORKSPACES = [
    ("small (6 sources)", "1ea7b2fa-b237-4bbd-801b-c9793d388984"),
    ("large (107 sources)", "c362f7b4-79a7-4ba7-98f7-c70d4beb0579"),
]


def prep(uuid):
    ws = db.get_aia_workspace(uuid)
    ws_id = ws["id"]
    source_ids = [s["id"] for s in db.get_aia_sources_by_workspace(ws_id)]
    lines = []
    for sid in source_ids:
        for ch in db.get_aia_chunks_by_source(sid):
            t = (ch.get("content") or "").strip().replace("\n", " ")
            if len(t) > 40:
                lines.append(t[:180])
            if len(lines) >= 150:
                break
        if len(lines) >= 150:
            break
    prov = get_embedding_provider()
    vecs = prov.embed(lines)
    vec_by_line = dict(zip(lines, vecs))

    def raw_search(line):
        try:
            qv = vec_by_line.get(line) or prov.embed_one(line)
            return db.hybrid_search_chunks(ws_id, line, qv, source_ids=source_ids, limit=10)
        except Exception:
            return []

    return lines, raw_search


def drop_index():
    with get_connection() as c:
        c.autocommit = True
        with c.cursor() as cur:
            cur.execute(f"DROP INDEX IF EXISTS {IDX}")
        c.autocommit = False


def build_index():
    with get_connection() as c:
        c.autocommit = True
        with c.cursor() as cur:
            cur.execute("SET max_parallel_maintenance_workers = 0")
            cur.execute("SET maintenance_work_mem = '512MB'")
            t0 = time.perf_counter()
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {IDX} ON aia_chunks "
                f"USING hnsw ((embedding::halfvec(2560)) halfvec_cosine_ops) "
                f"WHERE vector_dims(embedding) = 2560"
            )
            print(f"  (index rebuilt in {time.perf_counter() - t0:.0f}s)")
        c.autocommit = False


def measure(raw_search, lines):
    _parallel_search(lines[:8], raw_search)  # warm
    t0 = time.perf_counter()
    _parallel_search(lines, raw_search)
    return time.perf_counter() - t0


def main():
    prepped = [(label, *prep(uuid)) for label, uuid in WORKSPACES]

    print("\ndropping index -> measuring WITHOUT index ...")
    drop_index()
    without = {label: measure(rs, lines) for label, lines, rs in prepped}

    print("rebuilding index -> measuring WITH index ...")
    build_index()
    with_idx = {label: measure(rs, lines) for label, lines, rs in prepped}

    print("\n=== chip pre-search of 150 lines (parallel, real hybrid_search) ===")
    print(f"{'workspace':<22} {'no index':>10} {'with index':>12} {'speedup':>9}")
    for label, lines, rs in prepped:
        w0, w1 = without[label], with_idx[label]
        print(f"{label:<22} {w0:>9.2f}s {w1:>11.2f}s {w0 / w1:>8.1f}x")


if __name__ == "__main__":
    main()
