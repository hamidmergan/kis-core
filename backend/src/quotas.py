"""Per-user rate limiting / quota enforcement.

Each tool has its own independent counter and its own window. The window starts
with the first use of that tool and runs for the configured hours, so the
counter is only ever a count within a running window.

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


def _iso_z(ts: Optional[datetime]) -> Optional[str]:
    """UTC timestamp as ...Z, without a second zone marker from isoformat()."""
    if ts is None:
        return None
    return ts.astimezone(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


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
    The window is per tool and starts with the first use: the first consume sets
    reset_at, later ones in the same window leave it alone, and once it has
    passed the counter starts over at 1.
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

            # --- Ensure tool row exists ---
            cur.execute(
                """INSERT INTO user_quotas (user_id, quota_type, used)
                   VALUES (%s, %s, 0)
                   ON CONFLICT (user_id, quota_type) DO NOTHING""",
                (user_id, quota_type),
            )

            # --- Lock tool row ---
            cur.execute(
                """SELECT used, reset_at FROM user_quotas
                   WHERE user_id = %s AND quota_type = %s
                   FOR UPDATE""",
                (user_id, quota_type),
            )
            row = cur.fetchone()
            used = row["used"]
            reset_at: Optional[datetime] = row["reset_at"]
            if reset_at is not None and reset_at.tzinfo is None:
                reset_at = reset_at.replace(tzinfo=timezone.utc)

            # Without a running window the counter has no meaning.
            if reset_at is None or reset_at <= now:
                used = 0
                reset_at = None

            # --- Check limit ---
            if used >= limit:
                conn.rollback()
                return {
                    "allowed": False,
                    "used": used,
                    "limit": limit,
                    "reset_at": _iso_z(reset_at),
                }

            # --- Consume, starting a fresh window when none is running ---
            new_used = used + 1
            if reset_at is None:
                reset_at = now + timedelta(hours=window_hours)
                cur.execute(
                    """UPDATE user_quotas
                       SET used = %s, window_started_at = %s, reset_at = %s, updated_at = NOW()
                       WHERE user_id = %s AND quota_type = %s""",
                    (new_used, now, reset_at, user_id, quota_type),
                )
            else:
                cur.execute(
                    """UPDATE user_quotas
                       SET used = %s, updated_at = NOW()
                       WHERE user_id = %s AND quota_type = %s""",
                    (new_used, user_id, quota_type),
                )

        conn.commit()

    return {
        "allowed": True,
        "used": new_used,
        "limit": limit,
        "reset_at": _iso_z(reset_at),
    }


def enforce_quota(user_id: int, quota_type: str, is_admin: bool, locale: str = DEFAULT_LOCALE) -> None:
    """Check quota and raise HTTP 429 if the limit is exceeded.

    Call this before create_job() in each route handler.
    Retry jobs do NOT call this - quota was consumed at original submission.
    """
    result = check_and_consume_quota(user_id, quota_type, is_admin)
    if not result["allowed"]:
        cfg = QUOTA_DEFAULTS.get(quota_type, {})
        # Localized label, fall back to the static one in QUOTA_DEFAULTS, then to the quota_type key.
        label = t(f"quota.label.{quota_type}", locale)
        if label == f"quota.label.{quota_type}":
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
