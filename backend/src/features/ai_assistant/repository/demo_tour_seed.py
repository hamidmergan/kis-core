"""Marks that the guided tour's tool examples were copied in for a person once.

Kept apart from the examples themselves (aia_exercise_sets, aia_mindmaps,
aia_data_tables), because the whole point is that this row survives deleting
those.
"""

from src.core.db.pool import get_connection


def demo_tools_already_seeded(workspace_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM aia_demo_tools_seeded WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            return cur.fetchone() is not None


def mark_demo_tools_seeded(workspace_id: int, user_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_demo_tools_seeded (workspace_id, user_id)
                   VALUES (%s, %s)
                   ON CONFLICT (workspace_id, user_id) DO NOTHING""",
                (workspace_id, user_id),
            )
        conn.commit()
