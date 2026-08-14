
from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection


# ─── Per-user glossary reads ──────────────────────────────────────────────────

def get_aia_glossary_by_workspace(workspace_id: int, user_id: int) -> list[dict]:
    """One user's glossary across a whole workspace."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT g.id, g.term_de, g.term_en, g.base_form, g.definition, g.definition_en,
                          g.example_sentence, g.example_sentence_en, g.page_number,
                          s.filename,
                          MIN(c.start_time) AS start_time
                   FROM aia_glossary_entries g
                   JOIN aia_sources s ON s.id = g.source_id
                   LEFT JOIN aia_chunks c
                     ON c.source_id = g.source_id AND c.page_number = g.page_number
                   WHERE s.workspace_id = %s AND g.user_id = %s
                   GROUP BY g.id, s.filename
                   ORDER BY g.term_de""",
                (workspace_id, user_id),
            )
            return [dict(r) for r in cur.fetchall()]


def glossary_terms_used(workspace_id: int, user_id: int, tool: str) -> list[str]:
    """Die Glossarbegriffe, die diese Person in diesem Werkzeug schon hatte.

    Drei Einschraenkungen, jede mit Grund. Nach PERSON, denn ein Glossar gehoert der
    Person und was jemand anderes hatte, ist hier ohne Belang. Nach WERKZEUG, denn ein
    Begriff, der als Lernkarte dran war, ist als Karteikarte eine andere Uebung auf
    demselben Wort. Nach KURSRAUM, denn das Glossar wird per Kursraum gelesen, also
    gehoert das Gedaechtnis in denselben Rahmen.

    Woertlich, nicht normalisiert. Die Vergleichsform bildet der Aufrufer, damit hier
    keine zweite Meinung darueber entsteht, was zwei Begriffe gleich macht.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT i.glossary_term
                   FROM aia_exercise_items i
                   JOIN aia_exercise_sets s ON i.set_id = s.id
                   WHERE s.workspace_id = %s AND s.user_id = %s AND s.tool = %s
                     AND s.mode = 'glossary'
                     AND i.glossary_term IS NOT NULL AND i.glossary_term <> ''""",
                (workspace_id, user_id, tool),
            )
            return [row[0] for row in cur.fetchall()]


# ─── Per-user glossary writes ─────────────────────────────────────────────────

def bulk_create_glossary_entries(
    source_id: int,
    user_id: int,
    entries: list[dict],
) -> list[dict]:
    """Add entries to the user's personal glossary. Skips terms the user already
    has for this source (case-insensitive). Returns the newly inserted rows."""
    if not entries:
        return []
    inserted: list[dict] = []
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for e in entries:
                term = (e.get("term_de") or "").strip()
                if not term:
                    continue
                cur.execute(
                    """INSERT INTO aia_glossary_entries
                       (user_id, source_id, term_de, term_en, base_form, definition,
                        definition_en, example_sentence, example_sentence_en, page_number)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (user_id, source_id, lower(term_de)) DO NOTHING
                       RETURNING id, term_de""",
                    (
                        user_id,
                        source_id,
                        term,
                        e.get("term_en", ""),
                        e.get("base_form", ""),
                        e.get("definition", ""),
                        e.get("definition_en", ""),
                        e.get("example_sentence", ""),
                        e.get("example_sentence_en", ""),
                        e.get("page_number"),
                    ),
                )
                row = cur.fetchone()
                if row:
                    inserted.append(dict(row))
        conn.commit()
    return inserted


# ─── Delete ───────────────────────────────────────────────────────────────────

def delete_all_glossary_entries(workspace_id: int, user_id: int) -> int:
    """Delete every glossary entry this user has in the workspace. Returns count."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """DELETE FROM aia_glossary_entries g
                   USING aia_sources s
                   WHERE g.source_id = s.id
                     AND s.workspace_id = %s
                     AND g.user_id = %s""",
                (workspace_id, user_id),
            )
            count = cur.rowcount
        conn.commit()
    return count


def delete_glossary_entry(entry_id: int, user_id: int) -> bool:
    """Delete a single entry from one user's glossary."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """DELETE FROM aia_glossary_entries
                   WHERE id = %s AND user_id = %s
                   RETURNING id""",
                (entry_id, user_id),
            )
            deleted = cur.fetchone() is not None
        conn.commit()
    return deleted
