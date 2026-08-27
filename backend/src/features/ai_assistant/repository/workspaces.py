import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection


def create_aia_workspace(user_id: int, title: str, description: str | None) -> str:
    import uuid as _uuid
    workspace_uuid = str(_uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_workspaces (uuid, user_id, title, description)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (workspace_uuid, user_id, title, description),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    # Seed of grammar topics so a fresh course can be practised right away.
    from src.features.ai_assistant.repository.grammar_topics import seed_grammar_topics
    seed_grammar_topics(new_id, user_id)
    return workspace_uuid

def get_aia_workspace(uuid: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM aia_workspaces WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_aia_workspace_by_id(id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM aia_workspaces WHERE id = %s", (id,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_aia_workspaces_by_user(user_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM aia_workspaces WHERE user_id = %s ORDER BY last_visited_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def touch_aia_workspace_visited(uuid: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_workspaces SET last_visited_at = NOW() WHERE uuid = %s",
                (uuid,),
            )
        conn.commit()

def get_workspace_ids_with_tutors() -> set[int]:
    """Workspace ids that have at least one tutor, for the shared marker."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT workspace_id FROM aia_enrollments WHERE role = 'tutor'")
            return {r[0] for r in cur.fetchall()}


def get_aia_workspaces_for_member(user_id: int) -> list[dict]:
    """Course rooms the person joined through a link, with role and is_active."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT m.*, e.id AS enrollment_id, e.link_id, e.enrolled_until,
                          e.role AS member_role, e.via_demo,
                          al.code AS link_code, al.expires_at AS link_expires_at
                   FROM aia_workspaces m
                   JOIN aia_enrollments e ON e.workspace_id = m.id
                   LEFT JOIN aia_access_links al ON al.id = e.link_id
                   WHERE e.user_id = %s
                   ORDER BY e.created_at DESC""",
                (user_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def get_aia_workspaces_for_student(user_id: int) -> list[dict]:
    """Return workspaces with enrollment info. Same workspace can appear multiple times (different links)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT m.*, e.id AS enrollment_id, e.link_id, e.enrolled_until,
                          al.code AS link_code, al.expires_at AS link_expires_at
                   FROM aia_workspaces m
                   JOIN aia_enrollments e ON e.workspace_id = m.id
                   LEFT JOIN aia_access_links al ON al.id = e.link_id
                   WHERE e.user_id = %s AND m.is_active = TRUE
                   ORDER BY e.created_at DESC""",
                (user_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]

def get_demo_workspaces(viewer_id: int) -> list[dict]:
    """Active courses of all demo accounts, with a flag whether the viewer is already in."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT m.id, m.uuid, m.title, m.description,
                          (SELECT COUNT(*) FROM aia_sources s
                            WHERE s.workspace_id = m.id) AS source_count,
                          (e.id IS NOT NULL) AS joined,
                          COALESCE(e.via_demo, FALSE) AS via_demo,
                          (m.user_id = %s) AS owned
                     FROM aia_workspaces m
                     JOIN users u ON u.id = m.user_id
                     LEFT JOIN aia_enrollments e
                            ON e.workspace_id = m.id AND e.user_id = %s
                    WHERE u.is_demo AND m.is_active
                    ORDER BY m.title""",
                (viewer_id, viewer_id),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def update_aia_workspace(
    uuid: str, title: str, description: str | None, is_active: bool
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_workspaces
                   SET title = %s, description = %s, is_active = %s, updated_at = NOW()
                   WHERE uuid = %s""",
                (title, description, is_active, uuid),
            )
        conn.commit()

def set_aia_workspace_transcript_target_lang(uuid: str, lang: str) -> None:
    """The single language the owner translates media transcripts into (ISO code)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_workspaces
                   SET transcript_target_lang = %s, updated_at = NOW()
                   WHERE uuid = %s""",
                (lang, uuid),
            )
        conn.commit()

def set_aia_workspace_language_training(uuid: str, active: bool) -> None:
    """Whether the Sprachtrainer is offered in this workspace (owner decision)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_workspaces
                   SET language_training_active = %s, updated_at = NOW()
                   WHERE uuid = %s""",
                (active, uuid),
            )
        conn.commit()

def set_aia_workspace_diagnosis_language(uuid: str, lang: str) -> None:
    """The language the CEFR chat diagnosis is held in (ISO code)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_workspaces
                   SET diagnosis_language = %s, updated_at = NOW()
                   WHERE uuid = %s""",
                (lang, uuid),
            )
        conn.commit()

def set_aia_workspace_staff_note(uuid: str, text: str | None, links: list[dict]) -> None:
    """Owner-managed pinned note rendered above the sources list."""
    normalized_text = text.strip() if text else None
    if normalized_text == "":
        normalized_text = None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_workspaces
                   SET staff_note_text = %s,
                       staff_note_links = %s::jsonb,
                       updated_at = NOW()
                   WHERE uuid = %s""",
                (normalized_text, json.dumps(links), uuid),
            )
        conn.commit()


def update_aia_workspace_status(
    uuid: str,
    status: str,
    embedding_model: str | None = None,
    embedding_fingerprint: str | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_workspaces
                   SET status = %s,
                       embedding_model = COALESCE(%s, embedding_model),
                       embedding_fingerprint = COALESCE(%s, embedding_fingerprint),
                       updated_at = NOW()
                   WHERE uuid = %s""",
                (status, embedding_model, embedding_fingerprint, uuid),
            )
        conn.commit()

def set_aia_workspace_enroll_code(
    uuid: str, code: str, expires_at: datetime | None
) -> None:
    """Legacy: kept for backward compat. Prefer create_access_link."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_workspaces
                   SET enroll_code = %s, enroll_code_expires = %s, updated_at = NOW()
                   WHERE uuid = %s""",
                (code, expires_at, uuid),
            )
        conn.commit()

def delete_aia_workspace(uuid: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_workspaces WHERE uuid = %s", (uuid,))
        conn.commit()


# --- KI Tutor: Access Links ---

