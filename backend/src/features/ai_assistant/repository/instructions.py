"""The flag a result carries when the instruction named something the material lacks."""

from src.core.db.pool import get_connection

# The three result tables that carry a user instruction, nothing else may be updated here.
_TABLES = frozenset({"aia_mindmaps", "aia_data_tables", "aia_exercise_sets"})


def set_instruction_unmatched(table: str, row_id: int, unmatched: bool) -> None:
    """Writes the flag of one result row anew, the table name is checked against the list above."""
    if table not in _TABLES:
        raise ValueError(f"keine Anweisungstabelle: {table}")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {table} SET instruction_unmatched = %s WHERE id = %s",
                (bool(unmatched), row_id))
        conn.commit()
