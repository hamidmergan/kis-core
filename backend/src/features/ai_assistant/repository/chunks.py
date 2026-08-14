import os
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extras import RealDictCursor


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
# Min trigram word-similarity for the fuzzy keyword fallback in hybrid_search_chunks.
# 0.45 catches typos ("authoren" vs "Autoren" ≈ 0.55) without pulling unrelated words.
_FUZZY_WORD_SIM = 0.45
from src.core.db.pool import get_connection

# aia_chunks.embedding is 2560-dim (current global model qwen3-embedding-4b). That is over
# pgvector's 2000-dim limit for a `vector` ANN index, so the hnsw index is built on the
# halfvec(2560) form (halfvec indexes up to 4000 dims) as a PARTIAL index with predicate
# vector_dims=2560. Both the index and every query that wants it must use this exact dim.
# Changing the embedding model means re-embedding all chunks AND rebuilding the index.
_EMBED_INDEX_DIM = 2560
# hnsw scan tuning for the FILTERED workspace query: a selective source filter drops many of
# the global nearest neighbours, so iterative scan keeps pulling until it has a full top-80.
# relaxed_order is safe because callers re-sort candidates by vec_distance. This guarantees
# recall on the MAIN retrieval too (hybrid_search feeds context, not just chips). A plain scan
# with a big ef_search is ~10x faster on LARGE workspaces (~114ms -> ~10ms) at identical top-1,
# but can under-fill on very selective filters, so recall robustness wins over the ~10%
# end-to-end (vector search is only ~10% of a hybrid_search call anyway — the rest is the
# keyword/substring queries + RRF fusion).
_HNSW_EF_SEARCH = 100


def _vector_search_sql(source_filter: str) -> str:
    """Top-80 cosine vector search in the form that uses idx_chunks_embedding_hnsw.

    Casts to halfvec(2560) (the indexed expression) and carries the partial-index predicate
    vector_dims=2560 so the planner picks the hnsw index; without the cast it would full-scan.
    The predicate also means a future different-dim model neither breaks this query nor the
    index (those rows are simply not indexed and not returned). ``source_filter`` is a trusted
    fragment built by the caller, never user input."""
    d = _EMBED_INDEX_DIM
    return f"""SELECT c.id, c.page_number,
                    c.embedding::halfvec({d}) <=> %s::halfvec({d}) AS distance,
                    ROW_NUMBER() OVER (
                        ORDER BY c.embedding::halfvec({d}) <=> %s::halfvec({d})
                    ) AS rank
                FROM aia_chunks c
                JOIN aia_sources s ON s.id = c.source_id
                WHERE s.workspace_id = %s {source_filter}
                  AND c.embedding IS NOT NULL
                  AND vector_dims(c.embedding) = {d}
                ORDER BY c.embedding::halfvec({d}) <=> %s::halfvec({d})
                LIMIT 80"""


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
                   VALUES (%s, %s, %s, to_tsvector('simple', %s), %s, %s)
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

def find_chunks_containing(workspace_id: int, needle: str,
                           source_ids: list[int] | None = None,
                           limit: int = 4) -> list[dict]:
    """Chunks of a workspace whose text carries ``needle`` verbatim, oldest page first.

    A citation lookup, not a search: vector retrieval ranks by what a passage is ABOUT,
    and the passage that merely talks about office hours beats the slide that states
    "17:30-18:30 Uhr" — measured 0.398 against 0.656, i.e. the slide was not even inside
    the citation gate. A reader checking a time looks the time up; this is that lookup.
    Deliberately dumb (case-insensitive containment) so it holds for a clock time, a date,
    a section sign or a formula alike.
    """
    if not needle:
        return []
    where = ["s.workspace_id = %s", "c.content ILIKE %s"]
    params: list = [workspace_id, f"%{needle}%"]
    if source_ids:
        where.append("c.source_id = ANY(%s)")
        params.append(list(source_ids))
    params.append(limit)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""SELECT c.id, c.source_id, c.page_number, c.content,
                           c.start_time, c.end_time
                    FROM aia_chunks c JOIN aia_sources s ON s.id = c.source_id
                    WHERE {' AND '.join(where)}
                    ORDER BY c.page_number NULLS LAST, c.id
                    LIMIT %s""",
                params,
            )
            return [dict(row) for row in cur.fetchall()]


def get_page_text(source_id: int, page_number: int | None) -> str:
    """Concatenated chunk text of ONE page of a source (ordered), or "" when the
    page has no text chunk. Used to give the glossary definition prompt the real
    surrounding context of a marked term instead of the bare word."""
    if page_number is None:
        return ""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT content FROM aia_chunks
                   WHERE source_id = %s AND page_number = %s
                   ORDER BY id""",
                (source_id, page_number),
            )
            return "\n".join(r[0] for r in cur.fetchall() if r[0])


def get_source_page_numbers(source_id: int) -> set[int]:
    """Return the set of REAL page numbers for a source: the pages that have a
    text/OCR chunk. Used to validate citation pages against pages that actually
    exist (covers image/scanned pages that were OCR'd, while rejecting fully
    hallucinated numbers)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT page_number FROM aia_chunks WHERE source_id = %s",
                (source_id,),
            )
            return {row[0] for row in cur.fetchall() if row[0] is not None}

def update_chunk_embedding(chunk_id: int, embedding: list[float]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_chunks SET embedding = %s::vector WHERE id = %s",
                (str(embedding), chunk_id),
            )
        conn.commit()

def hybrid_search_chunks(
    workspace_id: int,
    query_text: str,
    query_embedding: list[float],
    source_ids: list[int] | None = None,
    limit: int = 15,
    rrf_k: int = 60,
    fuzzy: bool = False,
) -> list[dict]:
    """Hybrid search: combines vector similarity + BM25 keyword search via RRF.

    ``fuzzy`` adds a trigram word-similarity fallback so a MISSPELLED query word
    ("authoren") still anchors the right chunk. It is a per-row word_similarity
    scan (no index), so enable it ONLY for the short user query — NOT for the
    post-hoc attribution, which fires once per answer line over clean text and
    would otherwise pay seconds of needless fuzzy scans (slow citation chips)."""

    source_filter = ""
    source_param: list = []
    if source_ids is not None:
        source_filter = "AND s.id = ANY(%s)"
        source_param = [source_ids]

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Iterative hnsw scan so the FILTERED workspace query still gets a full top-80
            # (harmless no-op on the keyword/substring queries below and when no hnsw index
            # exists yet — the vector query then just full-scans).
            cur.execute("SET hnsw.iterative_scan = relaxed_order")
            cur.execute("SET hnsw.ef_search = %s", (_HNSW_EF_SEARCH,))
            # 1) Vector search (top 80). Keep the raw cosine distance: it is the
            # stopword-immune relevance signal (embeddings capture meaning, so a
            # conversational query like "erkläre mir bitte die X" still focuses on
            # X). Callers use it to tell a genuinely on-topic source from one that
            # only shares filler words. Uses the halfvec hnsw index (see _vector_search_sql).
            cur.execute(
                _vector_search_sql(source_filter),
                [str(query_embedding), str(query_embedding), workspace_id] + source_param + [str(query_embedding)],
            )
            vec_rows = cur.fetchall()
            vec_distance = {row["id"]: float(row["distance"]) for row in vec_rows}

            # 2) Keyword search (top 80) - OR conjunction so individual search terms match
            cur.execute(
                f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(c.search_vector,
                            (regexp_replace(plainto_tsquery('simple', %s)::text, ' & ', ' | ', 'g'))::tsquery
                        ) DESC
                    ) AS rank
                    FROM aia_chunks c
                    JOIN aia_sources s ON s.id = c.source_id
                    WHERE s.workspace_id = %s {source_filter}
                      AND c.search_vector IS NOT NULL
                      AND c.search_vector @@ (regexp_replace(plainto_tsquery('simple', %s)::text, ' & ', ' | ', 'g'))::tsquery
                    LIMIT 80""",
                [query_text, workspace_id] + source_param + [query_text],
            )
            kw_rows = cur.fetchall()

            # 2b) Exact substring fallback (catches proper names / out-of-vocab terms).
            # Stopwords spans DE + EN to keep ILIKE searches focused on content words
            # regardless of source / query language.
            _stop = {
                # German
                "der","die","das","ein","eine","und","oder","ist","hat","war","wer","was","wie","wo",
                "mit","von","für","auf","aus","bei","den","dem","des","als","nach","über","vor","bis",
                "wenn","dass","aber","auch","noch","nur","doch","sehr","wird","sind","kann","mehr",
                "nicht","sich","gibt","diese","einer","einem","einen","welche","welcher","welches",
                # English
                "the","and","or","of","is","in","to","a","an","was","that","this","for","with","on",
                "at","by","from","as","it","be","are","were","has","had","have","not","but","so",
                "if","then","do","does","did","what","which","who","when","where","why","how",
            }
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
                        WHERE s.workspace_id = %s {source_filter}
                          AND {ilike_clauses}
                        LIMIT 40""",
                    [workspace_id] + source_param + ilike_params,
                )
                ilike_rows = cur.fetchall()
                if ilike_rows:
                    kw_rows = kw_rows + ilike_rows

            # 2c) Fuzzy (typo-tolerant) fallback. A misspelled query word still
            # matches a trigram-similar WORD in the text ("authoren" -> "Autoren"),
            # so the answer-bearing chunk is retrieved even when the exact token (and
            # thus its high BM25 rank) is lost. Language-agnostic (character trigrams,
            # no word lists). Only words >= 4 chars — shorter ones match too loosely.
            # Ranked by best similarity so the closest match leads the RRF fusion.
            fuzzy_words = [w for w in words if len(w) >= 4]
            if fuzzy and fuzzy_words:
                best_sim = "GREATEST(" + ", ".join(["word_similarity(%s, c.content)"] * len(fuzzy_words)) + ")"
                sim_clauses = " OR ".join(["word_similarity(%s, c.content) >= %s"] * len(fuzzy_words))
                sim_params: list = []
                for w in fuzzy_words:
                    sim_params += [w, _FUZZY_WORD_SIM]
                cur.execute(
                    f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                            ORDER BY {best_sim} DESC
                        ) AS rank
                        FROM aia_chunks c
                        JOIN aia_sources s ON s.id = c.source_id
                        WHERE s.workspace_id = %s {source_filter}
                          AND ({sim_clauses})
                        LIMIT 40""",
                    list(fuzzy_words) + [workspace_id] + source_param + sim_params,
                )
                fuzzy_rows = cur.fetchall()
                if fuzzy_rows:
                    kw_rows = kw_rows + fuzzy_rows

            # 3) RRF fusion
            scores: dict[int, float] = {}
            for row in vec_rows:
                scores[row["id"]] = scores.get(row["id"], 0) + 1.0 / (rrf_k + row["rank"])
            # Keyword hits (BM25 + exact-substring): the actual term-overlap signal.
            # A chunk matched by vector ONLY is merely "semantically near" and may
            # be off-topic — callers use kw_hit to tell the two apart.
            kw_ids = {row["id"] for row in kw_rows}
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
                    chunk["kw_hit"] = cid in kw_ids
                    chunk["vec_distance"] = vec_distance.get(cid)  # cosine distance, None if kw-only
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

