"""Burst block for the chat: counter in Redis, block in the database."""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from loguru import logger

from src.core.db.pool import get_connection
from src.i18n import t
from src.limits import (
    RATE_LIMIT_BURST_REQUESTS,
    RATE_LIMIT_BURST_WINDOW_SECONDS,
    RATE_LIMIT_BLOCK_MINUTES,
    TOOL_BURST_REQUESTS,
    TOOL_BURST_WINDOW_SECONDS,
    TOOL_BURST_BLOCK_MINUTES,
    UPLOAD_HOURLY_MAX,
    UPLOAD_HOURLY_WINDOW_SECONDS,
)

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
_TZ_BERLIN = ZoneInfo("Europe/Berlin")


def _redis():
    """Redis client with short timeouts (pattern matches the rest of the project)."""
    import redis as _redis_lib
    return _redis_lib.from_url(_REDIS_URL, socket_connect_timeout=1, socket_timeout=1)


def _get_blocked_until(user_id: int) -> Optional[datetime]:
    """Read ``users.chat_blocked_until`` for this user. None if not blocked."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT chat_blocked_until FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
    if not row or not row[0]:
        return None
    blocked_until: datetime = row[0]
    if blocked_until.tzinfo is None:
        blocked_until = blocked_until.replace(tzinfo=timezone.utc)
    return blocked_until


def _set_blocked_until(user_id: int, blocked_until: datetime) -> None:
    """Set ``users.chat_blocked_until``. An existing value is overwritten."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET chat_blocked_until = %s WHERE id = %s",
                (blocked_until, user_id),
            )
        conn.commit()


def _format_block_message(blocked_until: datetime, locale: str = "de") -> str:
    """Localized error message with local Berlin time."""
    local = blocked_until.astimezone(_TZ_BERLIN)
    return t("rateLimit.blocked", locale, time=local.strftime("%H:%M"))


def enforce_burst(user_id: int, locale: str = "de") -> None:
    """Raises 429 when the user is blocked or breaks the burst limit."""
    if user_id <= 0:
        return

    now = datetime.now(timezone.utc)

    # 1. Existing block?
    blocked_until = _get_blocked_until(user_id)
    if blocked_until and blocked_until > now:
        raise HTTPException(
            status_code=429,
            detail={
                "message": _format_block_message(blocked_until, locale),
                "kind": "chat_blocked",
                "blocked_until": blocked_until.isoformat(),
            },
            headers={"Retry-After": str(int((blocked_until - now).total_seconds()))},
        )

    # 2. Increment counter in Redis.
    redis_key = f"rl:burst:chat:{user_id}"
    try:
        r = _redis()
        pipe = r.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, RATE_LIMIT_BURST_WINDOW_SECONDS, nx=True)
        count, _ = pipe.execute()
        r.close()
    except Exception as e:
        logger.warning("Burst rate-limit Redis error (user={}): {}", user_id, e)
        return  # fail-open

    if count <= RATE_LIMIT_BURST_REQUESTS:
        return

    # 3. Limit exceeded -> set DB block, raise 429.
    new_block_until = now + timedelta(minutes=RATE_LIMIT_BLOCK_MINUTES)
    try:
        _set_blocked_until(user_id, new_block_until)
    except Exception as e:
        logger.error("Konnte chat_blocked_until nicht setzen (user={}): {}", user_id, e)
        # Raise 429 anyway - counter has already triggered.

    logger.warning(
        "Chat burst triggered: user={} count={}/{} -> blocked until {}",
        user_id, count, RATE_LIMIT_BURST_REQUESTS,
        new_block_until.astimezone(_TZ_BERLIN).strftime("%H:%M:%S"),
    )
    raise HTTPException(
        status_code=429,
        detail={
            "message": _format_block_message(new_block_until, locale),
            "kind": "chat_blocked",
            "blocked_until": new_block_until.isoformat(),
        },
        headers={"Retry-After": str(RATE_LIMIT_BLOCK_MINUTES * 60)},
    )


def enforce_tool_burst(user_id: int, tool_key: str, locale: str = "de") -> None:
    """Raises 429 on too many tool requests, one counter per tool."""
    if user_id <= 0:
        return

    now = datetime.now(timezone.utc)
    block_key = f"rl:burst:{tool_key}:block:{user_id}"
    counter_key = f"rl:burst:{tool_key}:count:{user_id}"

    try:
        r = _redis()
        blocked_ts = r.get(block_key)
        if blocked_ts:
            blocked_until = datetime.fromisoformat(blocked_ts.decode())
            if blocked_until > now:
                r.close()
                raise HTTPException(
                    status_code=429,
                    detail={
                        "message": _format_block_message(blocked_until, locale),
                        "kind": "tool_blocked",
                        "tool_key": tool_key,
                        "blocked_until": blocked_until.isoformat(),
                    },
                    headers={"Retry-After": str(int((blocked_until - now).total_seconds()))},
                )

        pipe = r.pipeline()
        pipe.incr(counter_key)
        pipe.expire(counter_key, TOOL_BURST_WINDOW_SECONDS, nx=True)
        count, _ = pipe.execute()

        if count <= TOOL_BURST_REQUESTS:
            r.close()
            return

        new_block_until = now + timedelta(minutes=TOOL_BURST_BLOCK_MINUTES)
        r.set(block_key, new_block_until.isoformat(), ex=TOOL_BURST_BLOCK_MINUTES * 60)
        r.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Tool burst rate-limit Redis error (tool={} user={}): {}", tool_key, user_id, e)
        return  # fail-open

    logger.warning(
        "Tool burst triggered: tool={} user={} count={}/{} -> blocked until {}",
        tool_key, user_id, count, TOOL_BURST_REQUESTS,
        new_block_until.astimezone(_TZ_BERLIN).strftime("%H:%M:%S"),
    )
    raise HTTPException(
        status_code=429,
        detail={
            "message": _format_block_message(new_block_until, locale),
            "kind": "tool_blocked",
            "tool_key": tool_key,
            "blocked_until": new_block_until.isoformat(),
        },
        headers={"Retry-After": str(TOOL_BURST_BLOCK_MINUTES * 60)},
    )


def enforce_aia_burst(user_id: int, locale: str = "de") -> None:
    """Backward-compatible alias for the AI tutor burst gate."""
    enforce_tool_burst(user_id, "aia", locale)


def check_upload_limit(user_id: int, locale: str = "de") -> None:
    """Rejects an upload only when the hourly limit is already full, without counting."""
    if user_id <= 0:
        return

    redis_key = f"rl:upload:hourly:{user_id}"
    try:
        r = _redis()
        count = int(r.get(redis_key) or 0)
        ttl = r.ttl(redis_key)
        r.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Upload hourly limit Redis error (user={}): {}", user_id, e)
        return  # fail-open

    if count >= UPLOAD_HOURLY_MAX:
        retry_after = max(ttl, 60) if ttl and ttl > 0 else UPLOAD_HOURLY_WINDOW_SECONDS
        raise HTTPException(
            status_code=429,
            detail={
                "message": t(
                    "rateLimit.uploadHourly",
                    locale,
                    limit=UPLOAD_HOURLY_MAX,
                    minutes=max(1, retry_after // 60),
                ),
                "kind": "upload_hourly",
                "limit": UPLOAD_HOURLY_MAX,
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


def record_upload(user_id: int) -> None:
    """Counts an accepted upload, errors stay without consequence."""
    if user_id <= 0:
        return

    redis_key = f"rl:upload:hourly:{user_id}"
    try:
        r = _redis()
        pipe = r.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, UPLOAD_HOURLY_WINDOW_SECONDS, nx=True)
        pipe.execute()
        r.close()
    except Exception as e:
        logger.warning("Upload hourly record Redis error (user={}): {}", user_id, e)
