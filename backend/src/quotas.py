"""Per-user rate limiting / quota enforcement.

Each tool has its own independent counter. Counters reset 4 hours after
the limit is first hit (staggered reset - no thundering herd).

Admin users bypass all checks entirely.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import HTTPException

from src.database import get_connection
from src.i18n import DEFAULT_LOCALE, t
from src.limits import QUOTA_DEFAULTS


def _effective_limit(user_id: int, quota_type: str) -> int:
    """Return the active limit for this user+type (override > default). -1 = unlimited."""
    from src.database import quota_get_override
    override = quota_get_override(user_id, quota_type)
    if override is not None:
        return override
    cfg = QUOTA_DEFAULTS.get(quota_type)
    return cfg["limit"] if cfg else 30


def check_and_consume_quota(
    user_id: int,
    quota_type: str,
    is_admin: bool,
) -> dict:
    """Atomically check quota and consume 1 unit.

    Returns:
        {"allowed": bool, "used": int, "limit": int, "reset_at": str | None}

    Admins always get allowed=True without any DB write.
    Uses a global per-user reset timer (user_quota_resets table): when any tool
    hits its limit a single reset timer is set for all tools of that user.
    """
    if is_admin:
        return {"allowed": True, "used": 0, "limit": -1, "reset_at": None}

    limit = _effective_limit(user_id, quota_type)
    if limit == -1:
        return {"allowed": True, "used": 0, "limit": -1, "reset_at": None}

    cfg = QUOTA_DEFAULTS.get(quota_type, {})
    window_hours = cfg.get("window_hours", 4)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            now = datetime.now(timezone.utc)

            # --- Global reset check ---
            cur.execute(
                "SELECT reset_at FROM user_quota_resets WHERE user_id = %s FOR UPDATE",
                (user_id,),
            )
            global_row = cur.fetchone()
            global_reset_at: Optional[datetime] = global_row["reset_at"] if global_row else None

            if global_reset_at is not None and global_reset_at.tzinfo is None:
                global_reset_at = global_reset_at.replace(tzinfo=timezone.utc)

            if global_reset_at is not None and global_reset_at <= now:
                # Timer expired: zero all tools for user and clear global reset
                cur.execute(
                    """UPDATE user_quotas
                       SET used = 0, window_started_at = NULL, reset_at = NULL, updated_at = NOW()
                       WHERE user_id = %s""",
                    (user_id,),
                )
                cur.execute("DELETE FROM user_quota_resets WHERE user_id = %s", (user_id,))
                global_reset_at = None

            # --- Ensure tool row exists ---
            cur.execute(
                """INSERT INTO user_quotas (user_id, quota_type, used)
                   VALUES (%s, %s, 0)
                   ON CONFLICT (user_id, quota_type) DO NOTHING""",
                (user_id, quota_type),
            )

            # --- Lock tool row ---
            cur.execute(
                """SELECT used FROM user_quotas
                   WHERE user_id = %s AND quota_type = %s
                   FOR UPDATE""",
                (user_id, quota_type),
            )
            row = cur.fetchone()
            used = row["used"]

            # --- Check limit ---
            if used >= limit:
                conn.rollback()
                return {
                    "allowed": False,
                    "used": used,
                    "limit": limit,
                    "reset_at": (global_reset_at.isoformat() + "Z") if global_reset_at else None,
                }

            # --- Consume ---
            new_used = used + 1
            cur.execute(
                """UPDATE user_quotas
                   SET used = %s, updated_at = NOW()
                   WHERE user_id = %s AND quota_type = %s""",
                (new_used, user_id, quota_type),
            )

            # --- Set global reset when limit is first hit ---
            if new_used >= limit and global_reset_at is None:
                global_reset_at = now + timedelta(hours=window_hours)
                cur.execute(
                    """INSERT INTO user_quota_resets (user_id, reset_at)
                       VALUES (%s, %s)
                       ON CONFLICT (user_id) DO UPDATE SET reset_at = EXCLUDED.reset_at""",
                    (user_id, global_reset_at),
                )

        conn.commit()

    return {
        "allowed": True,
        "used": new_used,
        "limit": limit,
        "reset_at": (global_reset_at.isoformat() + "Z") if global_reset_at else None,
    }


def enforce_quota(user_id: int, quota_type: str, is_admin: bool, locale: str = DEFAULT_LOCALE) -> None:
    """Check quota and raise HTTP 429 if the limit is exceeded.

    Call this before create_job() in each route handler.
    Retry jobs do NOT call this - quota was consumed at original submission.
    """
    result = check_and_consume_quota(user_id, quota_type, is_admin)
    if not result["allowed"]:
        cfg = QUOTA_DEFAULTS.get(quota_type, {})
        label = cfg.get("label", quota_type)
        reset_at = result.get("reset_at")
        reset_text = ""
        if reset_at:
            try:
                from zoneinfo import ZoneInfo
                dt = datetime.fromisoformat(reset_at.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Berlin"))
                reset_text = t("quota.resetAt", locale, time=dt.strftime("%H:%M"))
            except Exception:
                pass
        raise HTTPException(
            status_code=429,
            detail={
                "message": t("quota.limitReached", locale, label=label) + reset_text,
                "quota_type": quota_type,
                "label": label,
                "used": result["used"],
                "limit": result["limit"],
                "reset_at": reset_at,
            },
        )
