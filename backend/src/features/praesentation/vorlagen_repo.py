# backend/src/features/praesentation/vorlagen_repo.py
"""The rows of a person's saved templates, the files live in storage."""

from __future__ import annotations

import uuid

from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection

_FELDER = "id, name, stiltext, created_at, last_used_at"


def _zeile(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "stiltext": row["stiltext"] or "",
        "createdAt": row["created_at"].isoformat(),
        "lastUsedAt": row["last_used_at"].isoformat(),
    }


def list_for_user(user_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SELECT {_FELDER} FROM praesentation_vorlagen WHERE user_id = %s "
                        "ORDER BY created_at, id", (user_id,))
            return [_zeile(r) for r in cur.fetchall()]


def count(user_id: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM praesentation_vorlagen WHERE user_id = %s", (user_id,))
            return cur.fetchone()[0]


def get(user_id: int, vid: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SELECT {_FELDER} FROM praesentation_vorlagen WHERE user_id = %s AND id = %s",
                        (user_id, vid))
            row = cur.fetchone()
            return _zeile(row) if row else None


def create(user_id: int, name: str, stiltext: str) -> dict:
    vid = uuid.uuid4().hex
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"INSERT INTO praesentation_vorlagen (id, user_id, name, stiltext) "
                        f"VALUES (%s, %s, %s, %s) RETURNING {_FELDER}", (vid, user_id, name, stiltext))
            row = cur.fetchone()
        conn.commit()
        return _zeile(row)


def update(user_id: int, vid: str, name: str, stiltext: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"UPDATE praesentation_vorlagen SET name = %s, stiltext = %s "
                        f"WHERE user_id = %s AND id = %s RETURNING {_FELDER}", (name, stiltext, user_id, vid))
            row = cur.fetchone()
        conn.commit()
        return _zeile(row) if row else None


def delete(user_id: int, vid: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM praesentation_vorlagen WHERE user_id = %s AND id = %s", (user_id, vid))
            getroffen = cur.rowcount
        conn.commit()
        return getroffen > 0


def touch(vid: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE praesentation_vorlagen SET last_used_at = NOW() WHERE id = %s", (vid,))
        conn.commit()
