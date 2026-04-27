"""Burst-Sperre für Chat: schützt vor Bug-Loops und Skript-Missbrauch.

Mechanik in 2 Schritten:

1. **Counter (Redis)** — pro User wird gezählt wie viele Chat-Anfragen in
   ``RATE_LIMIT_BURST_WINDOW_SECONDS`` reinkommen. Schnell, atomar, mit TTL.

2. **Sperre (Postgres)** — sobald der Counter ``RATE_LIMIT_BURST_REQUESTS``
   übersteigt, wird ``users.chat_blocked_until`` auf jetzt + ``RATE_LIMIT_BLOCK_MINUTES``
   gesetzt. Solange das in der Zukunft liegt, wirft ``enforce_burst`` 429.

Warum DB statt nur Redis: die Sperre soll auch nach Backend-Restart gelten.
Redis-Wipe bricht den Schutz nicht (DB ist Wahrheit für "ist gesperrt?").

Bei Redis-Ausfall: fail-open (Counter funktioniert nicht, Sperre aus DB greift
trotzdem). Bei DB-Ausfall: ohnehin der ganze Service hin.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from loguru import logger

from src.core.db.pool import get_connection
from src.limits import (
    RATE_LIMIT_BURST_REQUESTS,
    RATE_LIMIT_BURST_WINDOW_SECONDS,
    RATE_LIMIT_BLOCK_MINUTES,
)

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
_TZ_BERLIN = ZoneInfo("Europe/Berlin")


def _redis():
    """Redis-Client mit kurzen Timeouts (Pattern wie im restlichen Projekt)."""
    import redis as _redis_lib
    return _redis_lib.from_url(_REDIS_URL, socket_connect_timeout=1, socket_timeout=1)


def _get_blocked_until(user_id: int) -> Optional[datetime]:
    """Lese ``users.chat_blocked_until`` für diesen User. None wenn nicht gesperrt."""
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
    """Setze ``users.chat_blocked_until``. Bestehender Wert wird überschrieben."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET chat_blocked_until = %s WHERE id = %s",
                (blocked_until, user_id),
            )
        conn.commit()


def _format_block_message(blocked_until: datetime) -> str:
    """Deutsche Fehlermeldung mit lokaler Berlin-Zeit."""
    local = blocked_until.astimezone(_TZ_BERLIN)
    return (
        f"Chat ist bis {local.strftime('%H:%M')} Uhr gesperrt "
        f"(zu viele Anfragen in kurzer Zeit). Bitte später erneut versuchen."
    )


def enforce_burst(user_id: int) -> None:
    """Wirft HTTP 429 wenn der User aktuell gesperrt ist oder das Burst-Limit überschreitet.

    Reihenfolge:
    1. DB-Sperre prüfen (überschrieb Redis-Counter, falls vorhanden).
    2. Redis-Counter atomar erhöhen.
    3. Wenn Limit überschritten: DB-Sperre setzen → 429.

    Bei ``user_id <= 0`` (anonym/admin-bypass): no-op.
    """
    if user_id <= 0:
        return

    now = datetime.now(timezone.utc)

    # 1. Bestehende Sperre?
    blocked_until = _get_blocked_until(user_id)
    if blocked_until and blocked_until > now:
        raise HTTPException(
            status_code=429,
            detail={
                "message": _format_block_message(blocked_until),
                "kind": "chat_blocked",
                "blocked_until": blocked_until.isoformat(),
            },
            headers={"Retry-After": str(int((blocked_until - now).total_seconds()))},
        )

    # 2. Counter in Redis hochzählen.
    redis_key = f"rl:burst:chat:{user_id}"
    try:
        r = _redis()
        pipe = r.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, RATE_LIMIT_BURST_WINDOW_SECONDS, nx=True)
        count, _ = pipe.execute()
        r.close()
    except Exception as e:
        logger.warning("Burst rate-limit Redis-Fehler (user={}): {}", user_id, e)
        return  # fail-open

    if count <= RATE_LIMIT_BURST_REQUESTS:
        return

    # 3. Limit gerissen → DB-Sperre setzen, 429 werfen.
    new_block_until = now + timedelta(minutes=RATE_LIMIT_BLOCK_MINUTES)
    try:
        _set_blocked_until(user_id, new_block_until)
    except Exception as e:
        logger.error("Konnte chat_blocked_until nicht setzen (user={}): {}", user_id, e)
        # Trotzdem 429 werfen — Counter hat schon ausgelöst.

    logger.warning(
        "Chat-Burst ausgelöst: user={} count={}/{} → gesperrt bis {}",
        user_id, count, RATE_LIMIT_BURST_REQUESTS,
        new_block_until.astimezone(_TZ_BERLIN).strftime("%H:%M:%S"),
    )
    raise HTTPException(
        status_code=429,
        detail={
            "message": _format_block_message(new_block_until),
            "kind": "chat_blocked",
            "blocked_until": new_block_until.isoformat(),
        },
        headers={"Retry-After": str(RATE_LIMIT_BLOCK_MINUTES * 60)},
    )
