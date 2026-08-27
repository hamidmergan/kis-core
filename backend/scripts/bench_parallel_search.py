"""Measures the speedup of the parallel evidence search."""
import time

from src import database as db
from src.services.aia_embeddings import get_embedding_provider
from src.features.ai_assistant.routes._helpers import _parallel_search

WS_UUID = "1ea7b2fa-b237-4bbd-801b-c9793d388984"


def main():
    ws = db.get_aia_workspace(WS_UUID)
    ws_id = ws["id"]
    sources = db.get_aia_sources_by_workspace(ws_id)
    source_ids = [s["id"] for s in sources]
    print(f"workspace id={ws_id}, {len(source_ids)} sources")

    # About 150 real chunk texts used as search lines.
    lines = []
    for sid in source_ids:
        for c in db.get_aia_chunks_by_source(sid):
            txt = (c.get("content") or "").strip().replace("\n", " ")
            if len(txt) > 40:
                lines.append(txt[:180])
            if len(lines) >= 150:
                break
        if len(lines) >= 150:
            break
    print(f"{len(lines)} query lines")

    prov = get_embedding_provider()
    vecs = prov.embed(lines)
    vec_by_line = dict(zip(lines, vecs))

    def raw_search(line):
        try:
            qv = vec_by_line.get(line) or prov.embed_one(line)
            return db.hybrid_search_chunks(ws_id, line, qv, source_ids=source_ids, limit=10)
        except Exception as e:
            print("search failed:", e)
            return []

    # Warm the pool / caches so the first run is not penalised.
    _parallel_search(lines[:8], raw_search, max_workers=4)

    print("\n-- worker sweep (same 150 lines) --")
    for w in (1, 4, 8, 12, 16, 20):
        t0 = time.perf_counter()
        _parallel_search(lines, raw_search, max_workers=w)
        print(f"workers={w:>2}: {time.perf_counter() - t0:.2f}s")

    t0 = time.perf_counter()
    seq = _parallel_search(lines, raw_search, max_workers=1)
    t_seq = time.perf_counter() - t0

    seq2 = _parallel_search(lines, raw_search, max_workers=1)  # baseline: is the QUERY itself stable?

    t0 = time.perf_counter()
    par = _parallel_search(lines, raw_search, max_workers=8)
    t_par = time.perf_counter() - t0

    def id_order(d, k):
        return [h.get("id") for h in d[k]]

    def id_set(d, k):
        return {h.get("id") for h in d[k]}

    def top_id(d, k):
        # what attribution actually uses: the hit with the smallest vec_distance
        hits = d[k]
        if not hits:
            return None
        return min(hits, key=lambda h: 9.0 if h.get("vec_distance") is None else h["vec_distance"]).get("id")

    keys = seq.keys()
    seq_vs_seq_order = sum(1 for k in keys if id_order(seq, k) != id_order(seq2, k))
    seq_vs_seq_set = sum(1 for k in keys if id_set(seq, k) != id_set(seq2, k))
    seq_vs_seq_top = sum(1 for k in keys if top_id(seq, k) != top_id(seq2, k))
    seq_vs_par_order = sum(1 for k in keys if id_order(seq, k) != id_order(par, k))
    seq_vs_par_set = sum(1 for k in keys if id_set(seq, k) != id_set(par, k))
    seq_vs_par_top = sum(1 for k in keys if top_id(seq, k) != top_id(par, k))

    print(f"\nSEQUENTIAL (workers=1): {t_seq:.2f}s for {len(seq)} unique lines")
    print(f"PARALLEL   (workers=8): {t_par:.2f}s for {len(par)} unique lines")
    print(f"speedup: {t_seq / t_par:.1f}x")
    print(f"\n-- correctness over {len(keys)} lines --")
    print(f"order  differs seq-vs-seq (query non-determinism baseline): {seq_vs_seq_order}")
    print(f"order  differs seq-vs-par                                 : {seq_vs_par_order}")
    print(f"SET    differs seq-vs-seq (baseline)                      : {seq_vs_seq_set}")
    print(f"SET    differs seq-vs-par                                 : {seq_vs_par_set}")
    print(f"TOP hit differs seq-vs-seq (baseline)                     : {seq_vs_seq_top}")
    print(f"TOP hit (min vec_distance = the chip) differs seq-vs-par  : {seq_vs_par_top}")


if __name__ == "__main__":
    main()
