"""Burst block for chat: protects against bug loops and script abuse.

Mechanics in 2 steps:

1. **Counter (Redis)** - per user, count how many chat requests come in within
   ``RATE_LIMIT_BURST_WINDOW_SECONDS``. Fast, atomic, with TTL.

2. **Block (Postgres)** - as soon as the counter exceeds ``RATE_LIMIT_BURST_REQUESTS``,
   ``users.chat_blocked_until`` is set to now + ``RATE_LIMIT_BLOCK_MINUTES``.
   While that lies in the future, ``enforce_burst`` raises 429.

Why DB instead of just Redis: the block should also apply after a backend restart.
A Redis wipe does not break the protection (DB is truth for "is blocked?").

On Redis outage: fail-open (counter does not work, block from DB still applies).
On DB outage: the whole service is down anyway.
"""

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
    """Raise HTTP 429 if the user is currently blocked or exceeds the burst limit.

    Order:
    1. Check DB block (takes precedence over Redis counter, if any).
    2. Atomically increment Redis counter.
    3. If limit exceeded: set DB block -> 429.

    With ``user_id <= 0`` (anonymous/admin bypass): no-op.
    """
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
    """Raise HTTP 429 if the user fires too many requests against a tool in a
    short window. Redis-only (no DB persistence): the 10-min block is short
    enough that surviving a backend restart isn't worth a schema change. On
    Redis outage: fail-open, the 4h-quota still applies as the second line of
    defense.

    ``tool_key`` is namespaced into the Redis key so each tool has its own
    counter and block (e.g. burst on TTS does not block screencast).
    """
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


def enforce_upload_limits(user_id: int, locale: str = "de") -> None:
    """Reject an upload only when it would exceed the hourly cap.

    There is deliberately NO concurrent in-flight limit: backpressure for the
    indexing pipeline belongs in the worker, not at the HTTP door. Celery's
    bounded worker concurrency (``--concurrency`` on the ``aia`` queue) already
    caps how many sources are indexed/summarised at once; extra uploads simply
    wait in the queue as ``pending``. The hourly cap stays as the abuse guard
    (alongside the per-workspace ceiling enforced by the caller). The counter is
    incremented only when the upload would be accepted, so rejected uploads do
    not consume the quota.
    """
    if user_id <= 0:
        return

    redis_key = f"rl:upload:hourly:{user_id}"
    try:
        r = _redis()
        pipe = r.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, UPLOAD_HOURLY_WINDOW_SECONDS, nx=True)
        count, _ = pipe.execute()
        # On overflow roll the counter back so the user can retry next hour
        # without being penalized for the rejected attempt.
        if count > UPLOAD_HOURLY_MAX:
            r.decr(redis_key)
        ttl = r.ttl(redis_key)
        r.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Upload hourly limit Redis error (user={}): {}", user_id, e)
        return  # fail-open

    if count > UPLOAD_HOURLY_MAX:
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
