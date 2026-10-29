"""The event in storage: config in settings, stamps in their own table, wrong tries in Redis."""
import json
import secrets
from datetime import datetime, timezone

from loguru import logger

from src.core.db.pool import get_connection
from src.features.admin.repository.settings import get_setting, set_setting
from src.features.event.service import CODE_ALPHABET, VISITOR_CODE_LENGTH, default_config
from src.limits import (
    EVENT_CODE_ATTEMPT_TTL_SECONDS,
    EVENT_CODE_LOCK_SECONDS,
    EVENT_CODE_MAX_ATTEMPTS,
    EVENT_RAFFLE_WITHDRAW_MAX_PER_HOUR,
    EVENT_RAFFLE_WITHDRAW_MAX_PER_HOUR_ALL,
)
from src.security.rate_limit import _redis

CONFIG_KEY = "event_config"


# --- configuration ------------------------------------------------------------

def get_config() -> dict:
    """The saved configuration, the seed where nothing was saved yet."""
    roh = get_setting(CONFIG_KEY)
    if not roh:
        return default_config()
    # A configuration saved before a setting existed lacks it, the default fills the gap.
    return {**default_config(), **json.loads(roh)}


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


def delete_stamps_for(visitor_hash: str) -> None:
    """Takes every stamp off one card, the visitor starts over."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM event_stamps WHERE visitor_hash = %s", (visitor_hash,))
        conn.commit()


def delete_all_stamps() -> None:
    """Empties every card at once, the numbers start at zero."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM event_stamps")
        conn.commit()


def _new_visitor_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(VISITOR_CODE_LENGTH))


def visitor_code(visitor_hash: str) -> str:
    """This visitor's own short code, made on the first real stamp, lets staff find the card to reset it."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM event_visitor_codes WHERE visitor_hash = %s", (visitor_hash,))
            row = cur.fetchone()
            if row:
                return row[0]
            for _ in range(5):
                cur.execute(
                    """INSERT INTO event_visitor_codes (visitor_hash, code) VALUES (%s, %s)
                       ON CONFLICT DO NOTHING RETURNING code""",
                    (visitor_hash, _new_visitor_code()),
                )
                row = cur.fetchone()
                if row:
                    conn.commit()
                    return row[0]
                cur.execute("SELECT code FROM event_visitor_codes WHERE visitor_hash = %s", (visitor_hash,))
                row = cur.fetchone()
                if row:
                    return row[0]
    raise RuntimeError("visitor code not stored")


def peek_visitor_code(visitor_hash: str) -> str:
    """This visitor's code if one was ever made, empty for a browser that only looked, never stamped."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM event_visitor_codes WHERE visitor_hash = %s", (visitor_hash,))
            row = cur.fetchone()
            return row[0] if row else ""


def visitor_hash_for_code(code: str) -> str | None:
    """The visitor behind a short code, told at a stand, None once no one holds it."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT visitor_hash FROM event_visitor_codes WHERE code = %s", (code,))
            row = cur.fetchone()
            return row[0] if row else None


def delete_all_visitor_codes() -> None:
    """Drops every visitor's code along with their stamps, a full reset leaves nothing behind."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM event_visitor_codes")
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


# --- raffle -------------------------------------------------------------------

def raffle_email_for(visitor_hash: str) -> str | None:
    """The address this visitor entered, None while the visitor is not in the raffle."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM event_raffle_entries WHERE visitor_hash = %s", (visitor_hash,))
            row = cur.fetchone()
            return row[0] if row else None


def save_raffle_entry(visitor_hash: str, email: str) -> None:
    """One entry per card and per address, a new entry replaces whatever either of them had."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM event_raffle_entries WHERE visitor_hash = %s OR email = %s",
                (visitor_hash, email),
            )
            cur.execute(
                "INSERT INTO event_raffle_entries (visitor_hash, email) VALUES (%s, %s)",
                (visitor_hash, email),
            )
        conn.commit()


def delete_raffle_entry_by_email(email: str) -> bool:
    """Takes an address out of the raffle, True when it was in."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM event_raffle_entries WHERE email = %s RETURNING id", (email,))
            weg = cur.fetchone() is not None
        conn.commit()
    return weg


def delete_raffle_entry(entry_id: int) -> bool:
    """Removes one entry from the admin list, True when it existed."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM event_raffle_entries WHERE id = %s RETURNING id", (entry_id,))
            weg = cur.fetchone() is not None
        conn.commit()
    return weg


def delete_all_raffle_entries() -> None:
    """Empties the raffle, done once the winners are told."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM event_raffle_entries")
        conn.commit()


def raffle_entries() -> list[dict]:
    """Every entry for the admin, newest first, times in epoch milliseconds."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, entered_at FROM event_raffle_entries ORDER BY entered_at DESC, id DESC")
            return [
                {"id": int(entry_id), "email": email, "enteredAt": _epoch_ms(entered_at)}
                for entry_id, email, entered_at in cur.fetchall()
            ]


def _withdraw_key(visitor_hash: str) -> str:
    return f"event:raffle:withdraw:{visitor_hash}"


def withdraw_allowed(visitor_hash: str) -> bool:
    """Counts a withdraw request for this browser and for everyone, over either limit it waits, Redis trouble lets it through."""
    try:
        r = _redis()
        eigener = int(r.incr(_withdraw_key(visitor_hash)))
        r.expire(_withdraw_key(visitor_hash), 3600, nx=True)
        alle = int(r.incr(_withdraw_key("all")))
        r.expire(_withdraw_key("all"), 3600, nx=True)
        r.close()
    except Exception as fehler:
        logger.warning("Event raffle withdraw Redis error: {}", fehler)
        return True
    return eigener <= EVENT_RAFFLE_WITHDRAW_MAX_PER_HOUR and alle <= EVENT_RAFFLE_WITHDRAW_MAX_PER_HOUR_ALL


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


def clear_failures(visitor_hash: str) -> None:
    """Forgets wrong tries and lock of one visitor, Redis trouble stays silent."""
    try:
        r = _redis()
        r.delete(_count_key(visitor_hash), _lock_key(visitor_hash))
        r.close()
    except Exception as fehler:
        logger.warning("Event code clear Redis error: {}", fehler)
