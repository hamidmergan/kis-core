"""Places of the campus map, replaced as a whole on every sync."""
import json

import psycopg2.extras

from src.core.db.pool import get_connection

_FIELDS = ("id", "code", "kind", "title", "description", "opening_hours", "facilities", "terms", "link")


def replace_places(places: list[dict]) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM campus_places")
            for p in places:
                cur.execute(
                    """INSERT INTO campus_places (id, code, kind, title, description, opening_hours, facilities, terms, link)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        p["id"], p.get("code"), p.get("kind") or "building",
                        json.dumps(p.get("title") or {}), json.dumps(p.get("description") or {}),
                        json.dumps(p.get("opening_hours") or {}), json.dumps(p.get("facilities") or []),
                        json.dumps(p.get("terms") or {}), json.dumps(p.get("link")) if p.get("link") else None,
                    ),
                )
        conn.commit()
    return len(places)


def all_places() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT {', '.join(_FIELDS)} FROM campus_places ORDER BY id")
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def place_count() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM campus_places")
            return cur.fetchone()[0]
