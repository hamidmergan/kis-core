"""Per-user terminology glossary persistence.

Backs the translation-tool glossary that previously lived only in the browser
(localStorage). Each row belongs to exactly one user; there is no sharing.
Returned dicts are already shaped for the API / frontend ``Glossary`` type:
``{id, name, entries, createdAt}``.
"""

import json
import uuid
from typing import Optional

from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection


def _row_to_glossary(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "entries": row["entries"] or {},
        "createdAt": row["created_at"].isoformat(),
    }


def list_user_glossaries(user_id: int) -> list[dict]:
    """All glossaries owned by the user, oldest first (creation order)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, name, entries, created_at
                   FROM user_glossaries
                   WHERE user_id = %s
                   ORDER BY created_at, id""",
                (user_id,),
            )
            return [_row_to_glossary(r) for r in cur.fetchall()]


def count_user_glossaries(user_id: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM user_glossaries WHERE user_id = %s",
                (user_id,),
            )
            return cur.fetchone()[0]


def create_user_glossary(user_id: int, name: str, entries: dict[str, str]) -> dict:
    gid = uuid.uuid4().hex
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO user_glossaries (id, user_id, name, entries)
                   VALUES (%s, %s, %s, %s::jsonb)
                   RETURNING id, name, entries, created_at""",
                (gid, user_id, name, json.dumps(entries)),
            )
            row = cur.fetchone()
        conn.commit()
        return _row_to_glossary(row)


def update_user_glossary(
    user_id: int,
    glossary_id: str,
    *,
    name: Optional[str] = None,
    entries: Optional[dict[str, str]] = None,
) -> Optional[dict]:
    """Partial update scoped to the owner. Returns the updated row, or None if
    the glossary does not exist for this user."""
    sets: list[str] = []
    params: list = []
    if name is not None:
        sets.append("name = %s")
        params.append(name)
    if entries is not None:
        sets.append("entries = %s::jsonb")
        params.append(json.dumps(entries))
    if not sets:
        # Nothing to change — return the current state (or None if absent).
        rows = [g for g in list_user_glossaries(user_id) if g["id"] == glossary_id]
        return rows[0] if rows else None

    sets.append("updated_at = NOW()")
    params.extend([glossary_id, user_id])
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""UPDATE user_glossaries SET {', '.join(sets)}
                    WHERE id = %s AND user_id = %s
                    RETURNING id, name, entries, created_at""",
                params,
            )
            row = cur.fetchone()
        conn.commit()
        return _row_to_glossary(row) if row else None


def delete_user_glossary(user_id: int, glossary_id: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_glossaries WHERE id = %s AND user_id = %s",
                (glossary_id, user_id),
            )
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
