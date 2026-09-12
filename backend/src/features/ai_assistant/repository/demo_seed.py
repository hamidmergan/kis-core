"""Marks which demo module already reached which person, one row per pair."""

from src.core.db.pool import get_connection


def claim_demo_seeding(workspace_id: int, user_id: int) -> bool:
    """Sets the mark and reports whether this call was the one that got it."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_demo_seeded (workspace_id, user_id)
                   VALUES (%s, %s)
                   ON CONFLICT (workspace_id, user_id) DO NOTHING
                   RETURNING user_id""",
                (workspace_id, user_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row is not None
