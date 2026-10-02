"""The event in storage: config in settings, stamps in their own table, wrong tries in Redis."""
import json
from datetime import datetime, timezone

from loguru import logger

from src.core.db.pool import get_connection
from src.features.admin.repository.settings import get_setting, set_setting
from src.features.event.service import default_config
from src.limits import (
    EVENT_CODE_ATTEMPT_TTL_SECONDS,
    EVENT_CODE_LOCK_SECONDS,
    EVENT_CODE_MAX_ATTEMPTS,
)
from src.security.rate_limit import _redis

CONFIG_KEY = "event_config"


# --- configuration ------------------------------------------------------------

def get_config() -> dict:
    """The saved configuration, the seed where nothing was saved yet."""
    roh = get_setting(CONFIG_KEY)
    return json.loads(roh) if roh else default_config()


def save_config(config: dict) -> None:
    """Overwrites the whole configuration, an edit always replaces what was there."""
    set_setting(CONFIG_KEY, json.dumps(config, ensure_ascii=False))


# --- stamps -------------------------------------------------------------------

def _epoch_ms(stamped_at: datetime) -> int:
    """The database keeps naive UTC timestamps, the browser wants milliseconds."""
    if stamped_at.tzinfo is None:
        stamped_at = stamped_at.replace(tzinfo=timezone.utc)
    return int(stamped_at.timestamp() * 1000)


def stamps_for(visitor_hash: str) -> dict[str, int]:
    """Every stamp of this visitor, stand id to the moment it was given."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT station_id, stamped_at FROM event_stamps WHERE visitor_hash = %s",
                (visitor_hash,),
            )
            return {station_id: _epoch_ms(stamped_at) for station_id, stamped_at in cur.fetchall()}


def add_stamp(visitor_hash: str, station_id: str) -> None:
    """Stamps once, a second visit of the same stand changes nothing."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO event_stamps (visitor_hash, station_id)
                   VALUES (%s, %s)
                   ON CONFLICT DO NOTHING""",
                (visitor_hash, station_id),
            )
        conn.commit()


def visits_by_station() -> dict[str, int]:
    """How many visitors stamped each stand."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT station_id, COUNT(*) FROM event_stamps GROUP BY station_id")
            return {station_id: int(anzahl) for station_id, anzahl in cur.fetchall()}


def complete_cards(station_ids) -> int:
    """Visitors who stamped every current stand, without stands nobody can be complete."""
    ids = list(station_ids)
    if not ids:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM (
                       SELECT visitor_hash FROM event_stamps
                       WHERE station_id = ANY(%s)
                       GROUP BY visitor_hash
                       HAVING COUNT(DISTINCT station_id) = %s
                   ) AS voll""",
                (ids, len(ids)),
            )
            return int(cur.fetchone()[0])


# --- wrong codes --------------------------------------------------------------
# Redis trouble never blocks a stand: without it there is no lock and every try counts as the first.

def _lock_key(visitor_hash: str) -> str:
    return f"event:code:lock:{visitor_hash}"


def _count_key(visitor_hash: str) -> str:
    return f"event:code:fail:{visitor_hash}"


def lock_state(visitor_hash: str, now_ms: int) -> tuple[int | None, int]:
    """The end of the lock in epoch milliseconds, or None, and the tries left before the next one."""
    try:
        r = _redis()
        sperre = r.get(_lock_key(visitor_hash))
        zaehler = r.get(_count_key(visitor_hash))
        r.close()
    except Exception as fehler:
        logger.warning("Event code lock Redis error: {}", fehler)
        return None, EVENT_CODE_MAX_ATTEMPTS
    bis = int(sperre) if sperre else None
    if bis is not None and bis <= now_ms:
        bis = None
    return bis, max(0, EVENT_CODE_MAX_ATTEMPTS - int(zaehler or 0))


def register_failure(visitor_hash: str, now_ms: int) -> tuple[int | None, int]:
    """Counts a wrong code, the last allowed one starts the lock and resets the counter."""
    try:
        r = _redis()
        zaehler = int(r.incr(_count_key(visitor_hash)))
        r.expire(_count_key(visitor_hash), EVENT_CODE_ATTEMPT_TTL_SECONDS)
        if zaehler >= EVENT_CODE_MAX_ATTEMPTS:
            bis = now_ms + EVENT_CODE_LOCK_SECONDS * 1000
            r.set(_lock_key(visitor_hash), bis, ex=EVENT_CODE_LOCK_SECONDS)
            r.delete(_count_key(visitor_hash))
            r.close()
            return bis, EVENT_CODE_MAX_ATTEMPTS
        r.close()
    except Exception as fehler:
        logger.warning("Event code failure Redis error: {}", fehler)
        return None, EVENT_CODE_MAX_ATTEMPTS
    return None, EVENT_CODE_MAX_ATTEMPTS - zaehler
