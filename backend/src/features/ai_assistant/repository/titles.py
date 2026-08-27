"""Changes the display name of a generated result in three tables."""

from src.core.db.pool import get_connection

# The length the title columns and the interface work with.
MAX_TITLE_LEN = 120

_TABLES = {
    "exercise_set": "aia_exercise_sets",
    "mindmap": "aia_mindmaps",
    "data_table": "aia_data_tables",
}


def clean_title(title: str | None) -> str:
    """Trimmed, inner whitespace collapsed and cut to the ceiling."""
    return " ".join((title or "").split())[:MAX_TITLE_LEN]


def update_artifact_title(kind: str, row_id: int, user_id: int, workspace_id: int,
                          title: str) -> bool:
    """True when exactly this row of this person in this course room was renamed."""
    table = _TABLES[kind]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {table} SET title = %s "
                "WHERE id = %s AND user_id = %s AND workspace_id = %s",
                (title, row_id, user_id, workspace_id),
            )
            updated = cur.rowcount > 0
        conn.commit()
    return updated
