import math
import os
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extras import RealDictCursor


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
# Minimum similarity for the typo tolerant fallback.
_FUZZY_WORD_SIM = 0.45
from src.core.db.pool import get_connection

# The hnsw index sits on halfvec(2560), queries must use the same form.
_EMBED_INDEX_DIM = 2560
# Incremental scanning so the filtered search gets its full 80 hits.
_HNSW_EF_SEARCH = 100

# Question and stop words that drop out of a query, German and English.
_QUERY_STOPWORDS = {
    # Deutsch: Artikel, Praepositionen, Hilfsverben
    "der","die","das","ein","eine","und","oder","ist","hat","war","mit","von","für","fuer",
    "auf","aus","bei","den","dem","des","als","nach","über","ueber","vor","bis","wenn","dass",
    "aber","auch","noch","nur","doch","sehr","wird","sind","kann","mehr","nicht","sich","gibt",
    "diese","einer","einem","einen","muss","müssen","muessen","darf","dürfen","duerfen","soll",
    "sollen","im","am","um","zu","zur","zum","es","man","mir","mich","ich","sie","er","wir",
    # German question words, they almost never appear in the text carrying the answer.
    "wer","was","wie","wo","wann","warum","wieso","weshalb","wem","wen","wessen","woher","wohin",
    "welche","welcher","welches","welchem","welchen",
    # Englisch
    "the","and","or","of","is","in","to","a","an","that","this","for","with","on","at","by",
    "from","as","it","be","are","were","has","had","have","not","but","so","if","then","do",
    "does","did","what","which","who","when","where","why","how","can","must","should","would",
}


# Word weights cached per workspace because one question triggers a search per source.
_IDF_TTL_SECONDS = 300.0
# Ceiling and minimum weight, the rarest words decide.
_KW_MAX_TERMS = 4
_KW_MIN_IDF = 0.7
_IDF_CACHE: dict[tuple[int, str], tuple[float, float]] = {}
_IDF_N_CACHE: dict[int, tuple[float, int]] = {}


def _term_idf(cur, workspace_id: int, terms: list[str]) -> list[tuple[str, float]]:
    """Weight per query word across the whole workspace, the missing piece of BM25."""
    import time as _time
    jetzt = _time.monotonic()

    n_eintrag = _IDF_N_CACHE.get(workspace_id)
    if n_eintrag is None or jetzt - n_eintrag[0] > _IDF_TTL_SECONDS:
        cur.execute(
            """SELECT count(*) FROM aia_chunks c
                 JOIN aia_sources s ON s.id = c.source_id
                WHERE s.workspace_id = %s""",
            (workspace_id,),
        )
        n_chunks = int(cur.fetchone()[0] or 0)
        _IDF_N_CACHE[workspace_id] = (jetzt, n_chunks)
    else:
        n_chunks = n_eintrag[1]
    if not n_chunks:
        return []

    fehlend = [w for w in terms
               if (e := _IDF_CACHE.get((workspace_id, w.lower()))) is None
               or jetzt - e[0] > _IDF_TTL_SECONDS]
    if fehlend:
        cur.execute(
            """SELECT t.w,
                      (SELECT count(*) FROM aia_chunks c
                         JOIN aia_sources s ON s.id = c.source_id
                        WHERE s.workspace_id = %s
                          AND c.search_vector @@ plainto_tsquery('simple', t.w)) AS df
                 FROM unnest(%s::text[]) AS t(w)""",
            (workspace_id, fehlend),
        )
        for row in cur.fetchall():
            _IDF_CACHE[(workspace_id, str(row["w"]).lower())] = (jetzt, float(row["df"] or 0))
        if len(_IDF_CACHE) > 20000:      # cap so the cache does not grow
            _IDF_CACHE.clear()

    out: list[tuple[str, float]] = []
    gesehen: set[str] = set()
    for w in terms:
        if w.lower() in gesehen:
            continue
        gesehen.add(w.lower())
        df = _IDF_CACHE.get((workspace_id, w.lower()), (0.0, 0.0))[1]
        if 0 < df <= n_chunks:
            out.append((w, math.log(n_chunks / df)))
    # Rarest first, then truncate, at least one stays.
    out.sort(key=lambda t: t[1], reverse=True)
    stark = [t for t in out if t[1] >= _KW_MIN_IDF] or out[:1]
    return stark[:_KW_MAX_TERMS]


def _content_words(query_text: str) -> list[str]:
    """The content-bearing words of a query, stop words removed."""
    return [w for w in (t.strip(".,;:!?\"'()[]") for t in query_text.split())
            if len(w) >= 2 and w.lower() not in _QUERY_STOPWORDS]


def _vector_search_sql(source_filter: str) -> str:
    """Vector search in the form that uses the halfvec hnsw index."""
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


def _seen_pages_filter(seen_pages: dict[int, set] | None) -> tuple[str, list]:
    """WHERE fragment that limits the evidence search to read sources and pages."""
    if not seen_pages:
        return "", []
    teile: list[str] = []
    params: list = []
    # Sorted so Postgres can reuse the query plan.
    for sid in sorted(seen_pages):
        pages = seen_pages[sid]
        if not pages:
            teile.append("(c.source_id = %s)")
            params.append(sid)
        else:
            teile.append("(c.source_id = %s AND c.page_number = ANY(%s))")
            params += [sid, sorted(pages)]
    # No branch for NULL, the column is NOT NULL.
    return " AND (" + " OR ".join(teile) + ")", params


_SEARCH_MODES = ("hybrid", "dense", "keyword")


def _rrf_fuse(vec_rows, kw_rows, rrf_k: int, mode: str = "hybrid"):
    """Merges the two hit lists over their ranks."""
    if mode not in _SEARCH_MODES:
        raise ValueError(f"unbekannter Suchmodus: {mode!r}")

    scores: dict[int, float] = {}
    if mode != "keyword":
        for row in vec_rows:
            scores[row["id"]] = scores.get(row["id"], 0) + 1.0 / (rrf_k + row["rank"])
    # Keyword hits are the real word overlap signal.
    kw_ids: set[int] = set()
    if mode != "dense":
        kw_ids = {row["id"] for row in kw_rows}
        for row in kw_rows:
            scores[row["id"]] = scores.get(row["id"], 0) + 1.0 / (rrf_k + row["rank"])
    return scores, kw_ids


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

def update_aia_chunk_content(chunk_id: int, content: str) -> None:
    """Rewrites a chunk's text, the keyword vector is rebuilt with it."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_chunks
                   SET content = %s, search_vector = to_tsvector('simple', %s)
                   WHERE id = %s""",
                (content, content, chunk_id),
            )
        conn.commit()


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
    """Chunks that carry the search text verbatim, earliest page first."""
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
    """The continuous text of a page, or an empty string without a text chunk."""
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
    """The page numbers that really exist, for checking cited pages."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT page_number FROM aia_chunks WHERE source_id = %s",
                (source_id,),
            )
            return {row[0] for row in cur.fetchall() if row[0] is not None}

def count_chunks_and_unembedded(source_id: int) -> tuple[int, int]:
    """How many chunks a source has and how many of them still lack a vector."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*), COUNT(*) FILTER (WHERE embedding IS NULL)
                   FROM aia_chunks WHERE source_id = %s""",
                (source_id,),
            )
            total, unembedded = cur.fetchone()
            return int(total), int(unembedded)


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
    mode: str = "hybrid",
    seen_pages: dict[int, set] | None = None,
) -> list[dict]:
    """Hybrid search of vector and keyword, merged over the ranks."""

    if mode not in _SEARCH_MODES:
        raise ValueError(f"unbekannter Suchmodus: {mode!r}")

    source_filter = ""
    source_param: list = []
    if source_ids is not None:
        source_filter = "AND s.id = ANY(%s)"
        source_param = [source_ids]

    # Attached to source_filter so all four arms inherit the filter alike.
    _seen_sql, _seen_param = _seen_pages_filter(seen_pages)
    source_filter += _seen_sql
    source_param += _seen_param

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Incremental hnsw scanning for the filtered search.
            cur.execute("SET hnsw.iterative_scan = relaxed_order")
            cur.execute("SET hnsw.ef_search = %s", (_HNSW_EF_SEARCH,))
            # Vector search, the raw cosine distance is kept as a stop-word-proof signal.
            vec_rows, vec_distance = [], {}
            if mode != "keyword":
                cur.execute(
                    _vector_search_sql(source_filter),
                    [str(query_embedding), str(query_embedding), workspace_id] + source_param + [str(query_embedding)],
                )
                vec_rows = cur.fetchall()
                vec_distance = {row["id"]: float(row["distance"]) for row in vec_rows}

            # Keyword search, ranked by the rarity of the matched words.
            words = _content_words(query_text) if mode != "dense" else []
            # Word by word fallback, otherwise plainto_tsquery joins everything with AND.
            _terms = (_term_idf(cur, workspace_id, words or query_text.split())
                      if mode != "dense" else [])
            if _terms:
                # Sum of the weights, density breaks a tie.
                _score = " + ".join(
                    f"(CASE WHEN c.search_vector @@ plainto_tsquery('simple', %s) THEN {idf:.6f} ELSE 0 END)"
                    for _w, idf in _terms
                )
                _any = " OR ".join(["c.search_vector @@ plainto_tsquery('simple', %s)"] * len(_terms))
                _wparams = [w for w, _i in _terms]
                cur.execute(
                    f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                            ORDER BY ({_score}) DESC,
                                     ts_rank_cd(c.search_vector,
                                         plainto_tsquery('simple', %s)) DESC
                        ) AS rank
                        FROM aia_chunks c
                        JOIN aia_sources s ON s.id = c.source_id
                        WHERE s.workspace_id = %s {source_filter}
                          AND c.search_vector IS NOT NULL
                          AND ({_any})
                        LIMIT 80""",
                    _wparams + [" ".join(_wparams), workspace_id] + source_param + _wparams,
                )
                kw_rows = cur.fetchall()
            else:
                kw_rows = []

            # Substring fallback for proper names and unknown technical terms.
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

            # Typo-tolerant fallback via trigrams, from four characters on.
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

            # 3) RRF fusion (see _rrf_fuse, which also explains mode)
            scores, kw_ids = _rrf_fuse(vec_rows, kw_rows, rrf_k, mode)

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

