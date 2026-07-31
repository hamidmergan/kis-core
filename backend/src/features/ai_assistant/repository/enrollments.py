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


def enroll_student(
    workspace_id: int, user_id: int, enrolled_until: datetime | None,
    link_id: int | None = None, role: str = "student",
) -> int | None:
    """Enroll a user. Returns enrollment id, or None if already enrolled here.

    ``role`` is copied from the link rather than looked up through ``link_id``
    later, because ``link_id`` is ON DELETE SET NULL: deleting a spent tutor link
    must not silently demote the tutor.

    The conflict target is the person, not the link, and matches the rule on the
    table. Two links clicked at the same moment both pass the check in the route,
    so this is where that race ends: quietly, with None, instead of a 500.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_enrollments (workspace_id, user_id, link_id, enrolled_until, role)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (workspace_id, user_id) DO NOTHING
                   RETURNING id""",
                (workspace_id, user_id, link_id, enrolled_until, role),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0] if row else None

def is_workspace_tutor(workspace_id: int, user_id: int) -> bool:
    """True if the user joined this workspace through a tutor link.

    Tutors manage the workspace exactly like its owner, so an expired
    enrollment still counts here: losing management rights mid-semester
    because a link ran out would be a trap.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM aia_enrollments "
                "WHERE workspace_id = %s AND user_id = %s AND role = 'tutor'",
                (workspace_id, user_id),
            )
            return cur.fetchone() is not None

def get_workspace_participants(workspace_id: int) -> list[dict]:
    """Everyone enrolled in a workspace, one entry per person.

    Someone who joined through several links has several enrollments but is one
    participant, so the strongest role wins and the earliest join date is kept.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT e.user_id,
                          u.display_name,
                          u.ldap_username,
                          BOOL_OR(e.role = 'tutor') AS is_tutor,
                          MIN(e.created_at)         AS joined_at,
                          MAX(e.enrolled_until)     AS enrolled_until
                   FROM aia_enrollments e
                   JOIN users u ON u.id = e.user_id
                   WHERE e.workspace_id = %s
                   GROUP BY e.user_id, u.display_name, u.ldap_username
                   ORDER BY BOOL_OR(e.role = 'tutor') DESC, u.display_name ASC""",
                (workspace_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def set_participant_role(workspace_id: int, user_id: int, role: str) -> int:
    """Promote or demote a participant. Returns how many enrollments changed.

    All of the person's enrollments in this workspace move together: rights
    belong to the person, not to the link they happened to arrive through.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_enrollments SET role = %s WHERE workspace_id = %s AND user_id = %s",
                (role, workspace_id, user_id),
            )
            geaendert = cur.rowcount
        conn.commit()
    return geaendert


def is_student_enrolled(workspace_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM aia_enrollments WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            return cur.fetchone() is not None

def get_enrollment(workspace_id: int, user_id: int, link_id: int | None = None) -> dict | None:
    """Get a specific enrollment by workspace, user, and optionally link."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if link_id is not None:
                cur.execute(
                    "SELECT * FROM aia_enrollments WHERE workspace_id = %s AND user_id = %s AND link_id = %s",
                    (workspace_id, user_id, link_id),
                )
            else:
                cur.execute(
                    "SELECT * FROM aia_enrollments WHERE workspace_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 1",
                    (workspace_id, user_id),
                )
            row = cur.fetchone()
    return dict(row) if row else None

def get_enrollment_by_id(enrollment_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM aia_enrollments WHERE id = %s", (enrollment_id,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_enrolled_user_ids(workspace_id: int) -> list[int]:
    """Distinct user ids of students currently enrolled in a workspace (active only)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT user_id FROM aia_enrollments "
                "WHERE workspace_id = %s AND (enrolled_until IS NULL OR enrolled_until > NOW())",
                (workspace_id,),
            )
            return [r[0] for r in cur.fetchall()]

def get_workspace_by_enroll_code(code: str) -> dict | None:
    """Legacy: check both access_links and workspaces table."""
    result = get_workspace_by_access_link_code(code)
    if result:
        return result[0]  # return just the workspace for backward compat
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM aia_workspaces
                   WHERE enroll_code = %s AND enroll_code_expires > NOW()""",
                (code,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


# --- KI Tutor: Sources ---

