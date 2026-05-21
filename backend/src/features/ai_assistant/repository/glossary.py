import os
from typing import Optional

from psycopg2.extras import RealDictCursor, execute_values

from src.core.db.pool import get_connection


# ─── User-facing glossary (active picks for one user) ─────────────────────────

def get_aia_glossary(source_id: int, user_id: int) -> list[dict]:
    """User-visible glossary for a single source. Returns the pool entries the
    user has actively picked (status='active'), with timing info if available."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT g.id, g.term_de, g.term_en, g.definition, g.definition_en,
                          g.example_sentence, g.example_sentence_en, g.page_number,
                          MIN(c.start_time) AS start_time
                   FROM aia_glossary_entries g
                   JOIN aia_user_glossary_picks p
                     ON p.entry_id = g.id AND p.user_id = %s AND p.status = 'active'
                   LEFT JOIN aia_chunks c
                     ON c.source_id = g.source_id AND c.page_number = g.page_number
                   WHERE g.source_id = %s
                   GROUP BY g.id
                   ORDER BY g.term_de""",
                (user_id, source_id),
            )
            return [dict(r) for r in cur.fetchall()]


def get_aia_glossary_by_workspace(workspace_id: int, user_id: int) -> list[dict]:
    """User-visible glossary across a whole workspace. Returns the pool entries
    the user has actively picked."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT g.id, g.term_de, g.term_en, g.definition, g.definition_en,
                          g.example_sentence, g.example_sentence_en, g.page_number,
                          s.filename,
                          MIN(c.start_time) AS start_time
                   FROM aia_glossary_entries g
                   JOIN aia_user_glossary_picks p
                     ON p.entry_id = g.id AND p.user_id = %s AND p.status = 'active'
                   JOIN aia_sources s ON s.id = g.source_id
                   LEFT JOIN aia_chunks c
                     ON c.source_id = g.source_id AND c.page_number = g.page_number
                   WHERE s.workspace_id = %s
                   GROUP BY g.id, s.filename
                   ORDER BY g.term_de""",
                (user_id, workspace_id),
            )
            return [dict(r) for r in cur.fetchall()]


# ─── Pool writes (workspace-shared entries) ───────────────────────────────────

def bulk_create_pool_entries(source_id: int, chunk_id: Optional[int], entries: list[dict]) -> list[dict]:
    """Insert entries into the workspace-shared pool. Does NOT create user picks."""
    if not entries:
        return []
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            values = []
            params: list = []
            for e in entries:
                values.append("(%s, %s, %s, %s, %s, %s, %s, %s, %s)")
                params.extend([
                    source_id,
                    chunk_id,
                    e["term_de"],
                    e["term_en"],
                    e["definition"],
                    e.get("definition_en", ""),
                    e.get("example_sentence", ""),
                    e.get("example_sentence_en", ""),
                    e.get("page_number"),
                ])
            cur.execute(
                f"""INSERT INTO aia_glossary_entries
                    (source_id, chunk_id, term_de, term_en, definition,
                     definition_en, example_sentence, example_sentence_en, page_number)
                    VALUES {', '.join(values)}
                    RETURNING id, term_de""",
                params,
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
        return rows


def bulk_create_glossary_entries(
    source_id: int,
    user_id: int,
    entries: list[dict],
    chunk_id: Optional[int] = None,
) -> list[dict]:
    """Add entries to the user's personal glossary, reusing pool rows where the
    same (source_id, term) already exists. Used by the /extract endpoint, so
    manually-added terms become reusable by other users in the workspace too.
    """
    if not entries:
        return []
    if chunk_id is None:
        chunk_id = _resolve_chunk_id_for_page(source_id, entries[0].get("page_number"))

    terms_lower = [(e.get("term_de") or "").strip().lower() for e in entries]
    existing_by_term = _get_pool_entry_ids_for_terms(source_id, [t for t in terms_lower if t])

    to_insert: list[dict] = []
    to_pick_ids: list[int] = []
    for e, term_lower in zip(entries, terms_lower):
        if not term_lower:
            continue
        existing_id = existing_by_term.get(term_lower)
        if existing_id:
            to_pick_ids.append(existing_id)
        else:
            to_insert.append(e)

    inserted_rows = bulk_create_pool_entries(source_id, chunk_id, to_insert) if to_insert else []
    to_pick_ids.extend(r["id"] for r in inserted_rows)
    if to_pick_ids:
        create_user_picks(user_id, to_pick_ids)
    return inserted_rows


def _get_pool_entry_ids_for_terms(source_id: int, terms_lower: list[str]) -> dict[str, int]:
    """Map lowercased term_de → entry id for the given source. Used to dedupe
    a fresh /extract batch against the existing pool."""
    if not terms_lower:
        return {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT lower(term_de), id
                   FROM aia_glossary_entries
                   WHERE source_id = %s AND lower(term_de) = ANY(%s)""",
                (source_id, terms_lower),
            )
            return {row[0]: row[1] for row in cur.fetchall()}


def _resolve_chunk_id_for_page(source_id: int, page_number: Optional[int]) -> Optional[int]:
    """Best-effort chunk lookup for a (source, page). Falls back to the first
    chunk of the source if there's no page match (e.g. media without pages)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if page_number is not None:
                cur.execute(
                    "SELECT id FROM aia_chunks WHERE source_id = %s AND page_number = %s ORDER BY id LIMIT 1",
                    (source_id, page_number),
                )
                row = cur.fetchone()
                if row:
                    return row[0]
            cur.execute(
                "SELECT id FROM aia_chunks WHERE source_id = %s ORDER BY id LIMIT 1",
                (source_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None


# ─── User picks (per-user glossary view) ──────────────────────────────────────

def create_user_picks(user_id: int, entry_ids: list[int]) -> int:
    """Mark pool entries as active picks for the given user. Idempotent:
    existing 'active' picks stay, 'hidden' picks are revived to 'active'."""
    if not entry_ids:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """INSERT INTO aia_user_glossary_picks (user_id, entry_id, status)
                   VALUES %s
                   ON CONFLICT (user_id, entry_id) DO UPDATE
                     SET status = 'active'
                   WHERE aia_user_glossary_picks.status <> 'active'""",
                [(user_id, eid, "active") for eid in entry_ids],
            )
            count = cur.rowcount
        conn.commit()
        return count


def get_user_glossary_pick_count(workspace_id: int, user_id: int) -> int:
    """Active picks for one user within a workspace."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM aia_user_glossary_picks p
                   JOIN aia_glossary_entries g ON g.id = p.entry_id
                   JOIN aia_sources s ON s.id = g.source_id
                   WHERE s.workspace_id = %s AND p.user_id = %s AND p.status = 'active'""",
                (workspace_id, user_id),
            )
            return cur.fetchone()[0]


def get_unpicked_pool_entries(
    source_ids: list[int],
    user_id: int,
    limit: int,
) -> list[dict]:
    """Pool entries from the given sources that this user has neither actively
    picked nor hidden. Returned in (source_id, chunk_id, id) order so terms
    surface in document order rather than randomly."""
    if not source_ids or limit <= 0:
        return []
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT g.id, g.source_id, g.chunk_id
                   FROM aia_glossary_entries g
                   WHERE g.source_id = ANY(%s)
                     AND NOT EXISTS (
                         SELECT 1 FROM aia_user_glossary_picks p
                         WHERE p.user_id = %s AND p.entry_id = g.id
                     )
                   ORDER BY g.source_id, g.chunk_id NULLS LAST, g.id
                   LIMIT %s""",
                (source_ids, user_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]


# ─── Chunk processing flag ────────────────────────────────────────────────────

def claim_next_unprocessed_chunk(source_ids: list[int]) -> Optional[dict]:
    """Atomically claim a random chunk that hasn't been LLM-searched yet for
    glossary terms. Two-stage random pick — first a random source that still
    has unprocessed chunks, then a random chunk within it. Without the source
    stage the pick would be weighted by chunk count, so a 100-chunk PDF would
    crowd out a 10-chunk slide deck. With it, every selected file gets equal
    airtime regardless of size. The ``glossary_processed`` flag still
    guarantees each chunk is visited at most once."""
    if not source_ids:
        return None
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """UPDATE aia_chunks
                   SET glossary_processed = TRUE
                   WHERE id = (
                       SELECT id FROM aia_chunks
                       WHERE NOT glossary_processed
                         AND source_id = (
                             SELECT source_id FROM aia_chunks
                             WHERE source_id = ANY(%s) AND NOT glossary_processed
                             GROUP BY source_id
                             ORDER BY random()
                             LIMIT 1
                         )
                       ORDER BY random()
                       LIMIT 1
                       FOR UPDATE SKIP LOCKED
                   )
                   RETURNING id, source_id, page_number, content, start_time""",
                (source_ids,),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None


def get_pool_terms_for_chunk(chunk_id: int) -> set[str]:
    """Lowercased term_de set already in the pool for one chunk — used to
    dedupe a fresh LLM batch before inserting."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT lower(term_de) FROM aia_glossary_entries WHERE chunk_id = %s",
                (chunk_id,),
            )
            return {row[0] for row in cur.fetchall()}


def get_pool_terms_for_workspace(workspace_id: int) -> set[str]:
    """Lowercased term_de set across the whole workspace pool — used to keep
    the LLM from re-proposing terms a sibling chunk already contributed."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT lower(g.term_de)
                   FROM aia_glossary_entries g
                   JOIN aia_sources s ON s.id = g.source_id
                   WHERE s.workspace_id = %s""",
                (workspace_id,),
            )
            return {row[0] for row in cur.fetchall()}


# ─── Delete / hide ────────────────────────────────────────────────────────────

def delete_aia_glossary(source_id: int, user_id: Optional[int] = None) -> None:
    """Delete pool entries for a source. If `user_id` is given, only hides the
    user's picks for entries in this source (leaves pool intact for others).
    With `user_id=None` deletes the pool rows themselves — used by
    source-deletion cleanup (FK cascade handles this implicitly)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is None:
                cur.execute("DELETE FROM aia_glossary_entries WHERE source_id = %s", (source_id,))
            else:
                cur.execute(
                    """UPDATE aia_user_glossary_picks p
                       SET status = 'hidden'
                       FROM aia_glossary_entries g
                       WHERE p.entry_id = g.id
                         AND g.source_id = %s
                         AND p.user_id = %s
                         AND p.status = 'active'""",
                    (source_id, user_id),
                )
        conn.commit()


def delete_all_glossary_entries(workspace_id: int, user_id: int) -> int:
    """Hide every active pick this user has in the workspace. Pool stays
    intact so other users (and a later 'generate' by the same user) keep
    access. Returns count of picks hidden."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_user_glossary_picks p
                   SET status = 'hidden'
                   FROM aia_glossary_entries g
                   JOIN aia_sources s ON s.id = g.source_id
                   WHERE p.entry_id = g.id
                     AND s.workspace_id = %s
                     AND p.user_id = %s
                     AND p.status = 'active'""",
                (workspace_id, user_id),
            )
            count = cur.rowcount
        conn.commit()
    return count


def delete_glossary_entry(entry_id: int, user_id: int) -> bool:
    """Hide a single entry from one user's glossary (pool entry survives)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_user_glossary_picks
                   SET status = 'hidden'
                   WHERE user_id = %s AND entry_id = %s AND status = 'active'
                   RETURNING entry_id""",
                (user_id, entry_id),
            )
            hidden = cur.fetchone() is not None
        conn.commit()
    return hidden


# ─── Exercise Sets ────────────────────────────────────────────────────────────
