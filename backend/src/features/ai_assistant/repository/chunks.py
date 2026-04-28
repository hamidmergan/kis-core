import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extras import RealDictCursor

from src.limits import MAX_RESULT_FILES, JOB_RETENTION_HOURS

_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection


def create_aia_chunk(
    source_id: int,
    page_number: int,
    content: str,
    start_time: float | None = None,
    end_time: float | None = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_chunks
                   (source_id, page_number, content, search_vector, start_time, end_time)
                   VALUES (%s, %s, %s, to_tsvector('german', %s), %s, %s)
                   RETURNING id""",
                (source_id, page_number, content, content, start_time, end_time),
            )
            chunk_id = cur.fetchone()[0]
        conn.commit()
    return chunk_id

def get_aia_chunks_by_source(source_id: int) -> list[dict]:
    """Return all chunks for a source (without embeddings), ordered by page/time."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, source_id, page_number, content, start_time, end_time
                   FROM aia_chunks
                   WHERE source_id = %s
                   ORDER BY COALESCE(start_time, 0), page_number""",
                (source_id,),
            )
            return [dict(row) for row in cur.fetchall()]

def update_chunk_embedding(chunk_id: int, embedding: list[float]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_chunks SET embedding = %s::vector WHERE id = %s",
                (str(embedding), chunk_id),
            )
        conn.commit()

def search_similar_chunks(
    module_id: int,
    query_embedding: list[float],
    source_ids: list[int] | None = None,
    limit: int = 5,
) -> list[dict]:
    params: list = [str(query_embedding), module_id]
    source_filter = ""
    if source_ids is not None:
        source_filter = "AND s.id = ANY(%s)"
        params.append(source_ids)
    params.append(limit)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""SELECT c.id, c.source_id, c.page_number, c.content,
                           c.start_time, c.end_time,
                           c.embedding <=> %s::vector AS distance
                    FROM aia_chunks c
                    JOIN aia_sources s ON s.id = c.source_id
                    WHERE s.module_id = %s {source_filter}
                      AND c.embedding IS NOT NULL
                    ORDER BY distance ASC
                    LIMIT %s""",
                params,
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]

def hybrid_search_chunks(
    module_id: int,
    query_text: str,
    query_embedding: list[float],
    source_ids: list[int] | None = None,
    limit: int = 15,
    rrf_k: int = 60,
) -> list[dict]:
    """Hybrid search: combines vector similarity + BM25 keyword search via RRF."""
    from loguru import logger

    source_filter = ""
    source_param: list = []
    if source_ids is not None:
        source_filter = "AND s.id = ANY(%s)"
        source_param = [source_ids]

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # 1) Vector search (top 40)
            cur.execute(
                f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                        ORDER BY c.embedding <=> %s::vector
                    ) AS rank
                    FROM aia_chunks c
                    JOIN aia_sources s ON s.id = c.source_id
                    WHERE s.module_id = %s {source_filter}
                      AND c.embedding IS NOT NULL
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT 40""",
                [str(query_embedding), module_id] + source_param + [str(query_embedding)],
            )
            vec_rows = cur.fetchall()

            # 2) Keyword search (top 40) - OR conjunction so individual search terms match
            cur.execute(
                f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(c.search_vector,
                            (regexp_replace(plainto_tsquery('german', %s)::text, ' & ', ' | ', 'g'))::tsquery
                        ) DESC
                    ) AS rank
                    FROM aia_chunks c
                    JOIN aia_sources s ON s.id = c.source_id
                    WHERE s.module_id = %s {source_filter}
                      AND c.search_vector IS NOT NULL
                      AND c.search_vector @@ (regexp_replace(plainto_tsquery('german', %s)::text, ' & ', ' | ', 'g'))::tsquery
                    LIMIT 40""",
                [query_text, module_id] + source_param + [query_text],
            )
            kw_rows = cur.fetchall()

            # 2b) Exact substring fallback (catches proper names / non-German terms)
            _stop = {"der","die","das","ein","eine","und","oder","ist","hat","war","wer","was","wie","wo",
                      "mit","von","für","auf","aus","bei","den","dem","des","als","nach","über","vor","bis",
                      "wenn","dass","aber","auch","noch","nur","doch","sehr","wird","sind","kann","mehr",
                      "nicht","sich","gibt","diese","einer","einem","einen","welche","welcher","welches"}
            words = [w for w in query_text.split() if len(w) >= 2 and w.lower() not in _stop]
            if words:
                ilike_clauses = " AND ".join(["c.content ILIKE %s"] * len(words))
                ilike_params = [f"%{w}%" for w in words]
                cur.execute(
                    f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                            ORDER BY c.id
                        ) AS rank
                        FROM aia_chunks c
                        JOIN aia_sources s ON s.id = c.source_id
                        WHERE s.module_id = %s {source_filter}
                          AND {ilike_clauses}
                        LIMIT 20""",
                    [module_id] + source_param + ilike_params,
                )
                ilike_rows = cur.fetchall()
                if ilike_rows:
                    kw_rows = kw_rows + ilike_rows

            # 3) RRF fusion
            scores: dict[int, float] = {}
            for row in vec_rows:
                scores[row["id"]] = scores.get(row["id"], 0) + 1.0 / (rrf_k + row["rank"])
            for row in kw_rows:
                scores[row["id"]] = scores.get(row["id"], 0) + 1.0 / (rrf_k + row["rank"])

            if not scores:
                return []

            # Fetch full chunk data for top results
            top_ids = sorted(scores, key=lambda i: scores[i], reverse=True)[:limit]
            cur.execute(
                """SELECT id, source_id, page_number, content, start_time, end_time
                   FROM aia_chunks WHERE id = ANY(%s)""",
                (top_ids,),
            )
            chunk_map = {r["id"]: dict(r) for r in cur.fetchall()}

            # Return in score order
            results = []
            for cid in top_ids:
                if cid in chunk_map:
                    chunk = chunk_map[cid]
                    chunk["hybrid_score"] = scores[cid]
                    results.append(chunk)

    return results


# --- KI Tutor: Messages ---

def get_chunks_by_source(source_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, page_number, content, start_time, end_time
                   FROM aia_chunks
                   WHERE source_id = %s
                   ORDER BY page_number, id""",
                (source_id,),
            )
            return [dict(r) for r in cur.fetchall()]


# --- KI Tutor: Glossary ---

