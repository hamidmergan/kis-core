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


def quota_get_override(user_id: int, quota_type: str) -> Optional[int]:
    """Return per-user override limit, or None if no override exists."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT limit_value FROM user_quota_overrides WHERE user_id = %s AND quota_type = %s",
                (user_id, quota_type),
            )
            row = cur.fetchone()
    return row[0] if row else None

def quota_set_override(user_id: int, quota_type: str, limit_value: int) -> None:
    """Upsert a per-user override. limit_value=-1 means unlimited."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_quota_overrides (user_id, quota_type, limit_value)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (user_id, quota_type)
                   DO UPDATE SET limit_value = EXCLUDED.limit_value, updated_at = NOW()""",
                (user_id, quota_type, limit_value),
            )
        conn.commit()

def quota_remove_override(user_id: int, quota_type: str) -> None:
    """Remove a per-user override so the user falls back to the global default."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_quota_overrides WHERE user_id = %s AND quota_type = %s",
                (user_id, quota_type),
            )
        conn.commit()

def quota_reset(user_id: int, quota_type: str) -> None:
    """Admin: immediately zero a user's quota counter and clear the global reset timer."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE user_quotas
                   SET used = 0, window_started_at = NULL, reset_at = NULL, updated_at = NOW()
                   WHERE user_id = %s AND quota_type = %s""",
                (user_id, quota_type),
            )
            cur.execute(
                "DELETE FROM user_quota_resets WHERE user_id = %s",
                (user_id,),
            )
        conn.commit()

def quota_get_all_for_user(user_id: int) -> tuple[list[dict], Optional[datetime]]:
    """Return all quota rows for a user (used, reset_at, override if any) plus the global reset_at."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT
                     COALESCE(q.quota_type, o.quota_type) AS quota_type,
                     COALESCE(q.used, 0)                  AS used,
                     q.reset_at,
                     o.limit_value                        AS override
                   FROM user_quotas q
                   FULL OUTER JOIN user_quota_overrides o
                     ON o.user_id = q.user_id AND o.quota_type = q.quota_type
                   WHERE COALESCE(q.user_id, o.user_id) = %s""",
                (user_id,),
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT reset_at FROM user_quota_resets WHERE user_id = %s",
                (user_id,),
            )
            gr = cur.fetchone()
            global_reset_at: Optional[datetime] = gr["reset_at"] if gr else None
    return [dict(row) for row in rows], global_reset_at

def quota_get_all_users_usage() -> list[dict]:
    """Admin: return all active users with quota data (used=0 if no activity yet)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT u.id AS user_id, u.ldap_username, u.display_name,
                          q.quota_type, COALESCE(q.used, 0) AS used, q.reset_at,
                          o.limit_value AS override
                   FROM users u
                   LEFT JOIN user_quotas q ON q.user_id = u.id
                   LEFT JOIN user_quota_overrides o
                     ON o.user_id = u.id AND o.quota_type = q.quota_type
                   WHERE u.active = 1
                   ORDER BY u.display_name, q.quota_type"""
            )
            rows = cur.fetchall()
            cur.execute("SELECT user_id, reset_at FROM user_quota_resets")
            global_resets = cur.fetchall()
    result = [dict(row) for row in rows]
    resets_by_uid = {gr["user_id"]: gr["reset_at"] for gr in global_resets}
    for row in result:
        uid = row["user_id"]
        gr_at = resets_by_uid.get(uid)
        row["global_reset_at"] = (gr_at.isoformat() + "Z") if gr_at else None
    return result

def quota_get_all_overrides() -> list[dict]:
    """Return all override rows with user display name."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT u.id AS user_id, u.ldap_username, u.display_name,
                          o.quota_type, o.limit_value
                   FROM user_quota_overrides o
                   JOIN users u ON u.id = o.user_id
                   ORDER BY u.display_name, o.quota_type"""
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


# --- KI Tutor: Modules ---

