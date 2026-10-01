"""Deletes a user account and everything hanging off it without a foreign key."""

import psycopg2.extras

from src.core.db.pool import get_connection

# Cleared strictly in order by user_id.
SWEEP_BY_USER_ID = (
    # Haengt an keinem Arbeitsbereich.
    "jobs",
    "aia_jobs",
    "user_presence",
    "user_quotas",
    "user_quota_overrides",
    "aia_llm_usage_log",
    # Hangs off a workspace, but possibly off someone else's.
    "aia_enrollments",
    "aia_workspace_favorites",
    "aia_messages",
    "aia_notes",
    "aia_mindmaps",
    "aia_data_tables",
    "aia_user_settings",
    "aia_streaks",
    "aia_glossary_entries",
    "aia_exercise_sets",
    "aia_exercise_progress",
    "aia_exercise_pool_seen",
    "aia_schedule_entries",
    "aia_schedule_jobs",
    "aia_schedule_processed_sources",
    "aia_demo_tools_seeded",
    "aia_demo_seeded",
)

# Tables with a user id that are deliberately not in the list above.
SONDERFALL = {
    "users": "die Zeile selbst, geht zuletzt",
    "aia_workspaces": "geht zuerst, damit die Kaskade greift",
    "user_glossaries": "haengt per Fremdschluessel an users(id)",
    "praesentation_vorlagen": "haengt per Fremdschluessel an users(id)",
    "aia_grammar_topics": "gehoert dem Arbeitsbereich, verliert nur den Urheber",
    "invites": "gehoert der eingeladenen Person, verliert nur den Urheber",
    "access_codes": "gehoert der Testrunde, verliert nur den Urheber",
    "evaluation_responses": "Antworten bleiben anonym stehen, user_id faellt per Fremdschluessel automatisch weg",
}


def count_user_footprint(user_id: int) -> dict:
    """The numbers for the confirmation before deleting."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT
                     (SELECT COUNT(*) FROM aia_workspaces
                       WHERE user_id = %(id)s) AS workspaces,
                     (SELECT COUNT(*) FROM aia_sources s
                        JOIN aia_workspaces w ON w.id = s.workspace_id
                       WHERE w.user_id = %(id)s) AS sources,
                     (SELECT COUNT(*) FROM aia_messages WHERE user_id = %(id)s) AS messages,
                     (SELECT COUNT(*) FROM jobs WHERE user_id = %(id)s) AS jobs,
                     (SELECT COUNT(*) FROM aia_enrollments WHERE user_id = %(id)s) AS enrollments""",
                {"id": user_id},
            )
            return dict(cur.fetchone())


def delete_user_completely(user_id: int) -> None:
    """Deletes workspaces, traces, the whitelist entry and finally the account."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_workspaces WHERE user_id = %s", (user_id,))
            for tabelle in SWEEP_BY_USER_ID:
                cur.execute(f"DELETE FROM {tabelle} WHERE user_id = %s", (user_id,))
            cur.execute(
                "UPDATE aia_grammar_topics SET created_by = NULL WHERE created_by = %s",
                (user_id,),
            )
            cur.execute(
                "UPDATE invites SET created_by = NULL WHERE created_by = %s",
                (user_id,),
            )
            cur.execute(
                "UPDATE access_codes SET created_by = NULL WHERE created_by = %s",
                (user_id,),
            )
            cur.execute(
                """DELETE FROM whitelist
                    WHERE email <> ''
                      AND LOWER(email) = (SELECT LOWER(email) FROM users WHERE id = %s)""",
                (user_id,),
            )
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
