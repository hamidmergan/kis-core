"""Chunks of the campus index and the hybrid search over them."""
import psycopg2.extras

from src.core.db.pool import get_connection
from src.core.db.schema_campus import CAMPUS_EMBED_INDEX_DIM
from src.features.ai_assistant.repository.chunks import _rrf_fuse

_RRF_K = 60
_ARM_LIMIT = 80


def replace_chunks(page_id: int, chunks: list[dict]) -> list[int]:
    """Drops the old chunks of a page and writes the new ones, returns their ids in order."""
    ids: list[int] = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM campus_chunks WHERE page_id = %s", (page_id,))
            for c in chunks:
                cur.execute(
                    """INSERT INTO campus_chunks (page_id, position, heading, content, search_vector)
                       VALUES (%s, %s, %s, %s, to_tsvector('simple', %s)) RETURNING id""",
                    (page_id, c["position"], c.get("heading"), c["content"], c["content"]),
                )
                ids.append(cur.fetchone()[0])
        conn.commit()
    return ids


def set_embedding(chunk_id: int, embedding: list[float]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE campus_chunks SET embedding = %s::vector WHERE id = %s", (str(list(embedding)), chunk_id))
        conn.commit()


def set_embeddings(pairs: list[tuple[int, list[float]]]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE campus_chunks SET embedding = %s::vector WHERE id = %s",
                [(str(list(vec)), cid) for cid, vec in pairs],
            )
        conn.commit()


_HIT_COLS = """c.id, c.page_id, c.position, c.heading, c.content,
               p.url, p.title, p.kind, p.filename, p.fetched_at"""


def hybrid_search(query_text: str, query_embedding: list[float] | None, limit: int) -> list[dict]:
    """Vector and keyword arm fused over their ranks, best first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            vec_rows: list = []
            if query_embedding is not None and len(query_embedding) == CAMPUS_EMBED_INDEX_DIM:
                cur.execute("SET LOCAL hnsw.ef_search = 100")
                cur.execute(
                    f"""SELECT c.id, ROW_NUMBER() OVER (ORDER BY c.embedding::halfvec({CAMPUS_EMBED_INDEX_DIM}) <=> %s::halfvec({CAMPUS_EMBED_INDEX_DIM})) AS rank
                        FROM campus_chunks c
                        WHERE c.embedding IS NOT NULL AND vector_dims(c.embedding) = {CAMPUS_EMBED_INDEX_DIM}
                        ORDER BY c.embedding::halfvec({CAMPUS_EMBED_INDEX_DIM}) <=> %s::halfvec({CAMPUS_EMBED_INDEX_DIM})
                        LIMIT %s""",
                    (str(list(query_embedding)), str(list(query_embedding)), _ARM_LIMIT),
                )
                vec_rows = cur.fetchall()
            elif query_embedding is not None:
                cur.execute(
                    """SELECT c.id, ROW_NUMBER() OVER (ORDER BY c.embedding <=> %s::vector) AS rank
                       FROM campus_chunks c
                       WHERE c.embedding IS NOT NULL AND vector_dims(c.embedding) = %s
                       ORDER BY c.embedding <=> %s::vector
                       LIMIT %s""",
                    (str(list(query_embedding)), len(query_embedding), str(list(query_embedding)), _ARM_LIMIT),
                )
                vec_rows = cur.fetchall()
            cur.execute(
                """SELECT c.id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.search_vector, q) DESC) AS rank
                   FROM campus_chunks c, websearch_to_tsquery('simple', %s) q
                   WHERE c.search_vector @@ q
                   LIMIT %s""",
                (query_text, _ARM_LIMIT),
            )
            kw_rows = cur.fetchall()
            scores, kw_ids = _rrf_fuse(vec_rows, kw_rows, _RRF_K)
            if not scores:
                return []
            top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
            ids = [cid for cid, _ in top]
            cur.execute(
                f"SELECT {_HIT_COLS} FROM campus_chunks c JOIN campus_pages p ON p.id = c.page_id WHERE c.id = ANY(%s)",
                (ids,),
            )
            by_id = {r["id"]: dict(r) for r in cur.fetchall()}
    hits = []
    for cid, score in top:
        row = by_id.get(cid)
        if row is None:
            continue
        row["score"] = score
        row["kw_hit"] = cid in kw_ids
        hits.append(row)
    return hits


def neighbors(page_id: int, position: int, span: int = 1) -> list[dict]:
    """The chunks right before and after one hit on the same page."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""SELECT {_HIT_COLS} FROM campus_chunks c JOIN campus_pages p ON p.id = c.page_id
                    WHERE c.page_id = %s AND c.position BETWEEN %s AND %s AND c.position <> %s
                    ORDER BY c.position""",
                (page_id, position - span, position + span, position),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def chunk_count() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM campus_chunks")
            return cur.fetchone()[0]
