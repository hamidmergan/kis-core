"""Renames a source and pulls every copy of the name in the generated material along."""

from psycopg2.extras import Json

from src.core.db.pool import get_connection

# The two keys a source name really appears under.
_NAME_KEYS = ("source_label", "filename")


def _relabel(value, old: str, new: str):
    """Recursively replaces every source name, but only under the name keys."""
    if isinstance(value, list):
        return [_relabel(v, old, new) for v in value]
    if isinstance(value, dict):
        return {
            k: (new if k in _NAME_KEYS and v == old else _relabel(v, old, new))
            for k, v in value.items()
        }
    return value


def _relabel_column(cur, table: str, column: str, where: str, params: tuple, old: str, new: str) -> None:
    """Rewrites a JSON column that holds source names as copies."""
    cur.execute(f"SELECT id, {column} FROM {table} {where}", params)
    zeilen = cur.fetchall()
    for row_id, value in zeilen:
        if value is None:
            continue
        neu = _relabel(value, old, new)
        if neu != value:
            cur.execute(f"UPDATE {table} SET {column} = %s WHERE id = %s", (Json(neu), row_id))


def rename_aia_source(source_uuid: str, new_filename: str) -> None:
    """Renames a source and pulls every copy of the name along."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, workspace_id, filename FROM aia_sources WHERE uuid = %s",
                (source_uuid,),
            )
            row = cur.fetchone()
            if row is None:
                return
            source_id, workspace_id, old_filename = row[0], row[1], row[2]
            if old_filename == new_filename:
                return

            cur.execute(
                "UPDATE aia_sources SET filename = %s WHERE id = %s",
                (new_filename, source_id),
            )
            # Exercises hang off the course room through their set, not off the source.
            cur.execute(
                """UPDATE aia_exercise_items AS i SET source_label = %s
                     FROM aia_exercise_sets AS s
                    WHERE i.set_id = s.id
                      AND s.workspace_id = %s
                      AND i.source_label = %s""",
                (new_filename, workspace_id, old_filename),
            )
            # The pool hangs off the source directly, no name comparison needed.
            cur.execute(
                "UPDATE aia_exercise_pool SET source_label = %s WHERE source_id = %s",
                (new_filename, source_id),
            )

            _relabel_column(
                cur, "aia_exercise_items", "sources",
                "WHERE set_id IN (SELECT id FROM aia_exercise_sets WHERE workspace_id = %s)",
                (workspace_id,), old_filename, new_filename,
            )
            _relabel_column(
                cur, "aia_exercise_pool", "sources",
                "WHERE source_id = %s", (source_id,), old_filename, new_filename,
            )
            _relabel_column(
                cur, "aia_mindmaps", "mindmap",
                "WHERE workspace_id = %s", (workspace_id,), old_filename, new_filename,
            )
            _relabel_column(
                cur, "aia_data_tables", "table_data",
                "WHERE workspace_id = %s", (workspace_id,), old_filename, new_filename,
            )
            _relabel_column(
                cur, "aia_data_tables", "sources",
                "WHERE workspace_id = %s", (workspace_id,), old_filename, new_filename,
            )
        conn.commit()
