import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extras import RealDictCursor

from src.limits import MAX_RESULT_FILES, JOB_RETENTION_HOURS

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
                   VALUES (%s, %s, %s, %s)""",
                (workspace_uuid, user_id, title, description),
            )
        conn.commit()
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
    """Workspaces the user joined via a link, with the role that link gave them.

    Deactivating a workspace hides it from students, but never from tutors:
    they manage it, so they need it even while it is switched off.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT m.*, e.id AS enrollment_id, e.link_id, e.enrolled_until,
                          e.role AS member_role,
                          al.code AS link_code, al.expires_at AS link_expires_at
                   FROM aia_workspaces m
                   JOIN aia_enrollments e ON e.workspace_id = m.id
                   LEFT JOIN aia_access_links al ON al.id = e.link_id
                   WHERE e.user_id = %s
                     AND (e.role = 'tutor' OR m.is_active = TRUE)
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

def set_aia_workspace_translation_mode(uuid: str, mode: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_workspaces
                   SET transcript_translation_mode = %s, updated_at = NOW()
                   WHERE uuid = %s""",
                (mode, uuid),
            )
        conn.commit()

def set_aia_workspace_transcript_default_lang(uuid: str, lang: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_workspaces
                   SET transcript_default_lang = %s, updated_at = NOW()
                   WHERE uuid = %s""",
                (lang, uuid),
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

