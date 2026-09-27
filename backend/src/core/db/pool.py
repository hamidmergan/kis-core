import os
import time
from contextlib import contextmanager
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool
from loguru import logger

from src.limits import DB_POOL_MAX_CONNECTIONS

_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


# A connection idle longer than this gets a quick test before use, it may have died meanwhile.
_IDLE_CHECK_SECONDS = 30
_last_used: dict[int, float] = {}


def reset_after_fork() -> None:
    """Drops the inherited pool in a forked worker, its sockets belong to the parent."""
    global _pool
    # Not closed on purpose: closing would end the parent's sessions as well.
    _pool = None
    _last_used.clear()


def _alive(conn) -> bool:
    """False for a connection the server has dropped, tested only after a longer idle time."""
    if conn.closed:
        return False
    if time.monotonic() - _last_used.get(id(conn), 0.0) < _IDLE_CHECK_SECONDS:
        return True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.rollback()
        return True
    except Exception:  # noqa: BLE001 - any failure here means the line is dead
        return False


def _keep_idle() -> int:
    """How many free connections a process keeps, the web backend more than a worker process."""
    try:
        return max(1, int(os.environ.get("DB_POOL_KEEP_IDLE", "3")))
    except ValueError:
        return 3


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        dsn = os.environ["DATABASE_URL"]
        # The ceiling must be above REQUEST_THREAD_LIMIT, see limits.py.
        _pool = psycopg2.pool.ThreadedConnectionPool(1, DB_POOL_MAX_CONNECTIONS, dsn)
        # psycopg2 closes every returned connection above minconn, raised after the start it keeps them without opening all at once.
        _pool.minconn = min(_keep_idle(), DB_POOL_MAX_CONNECTIONS)
    return _pool


@contextmanager
def run_once_across_processes(key: int):
    """Gives True to exactly one process and False to all others."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (key,))
            am_first = bool(cur.fetchone()[0])
            conn.commit()   # Transaktion beenden, der Riegel bleibt (sitzungsweit)

            if not am_first:
                # Wait for the first one, then release right away and do nothing.
                try:
                    cur.execute("SELECT pg_advisory_lock(%s)", (key,))
                    conn.commit()
                    cur.execute("SELECT pg_advisory_unlock(%s)", (key,))
                    conn.commit()
                except Exception as e:
                    logger.error("Warten auf Riegel {} fehlgeschlagen: {}", key, e)
                yield False
                return

            try:
                yield True
            finally:
                try:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (key,))
                    conn.commit()
                except Exception as e:
                    # Do not swallow it, a stuck lock blocks the next start.
                    logger.error("Advisory-Riegel {} nicht freigegeben: {}", key, e)


@contextmanager
def get_connection():
    pool = _get_pool()
    conn = pool.getconn()
    # After a database restart the pool still holds dead lines, those are swapped for fresh ones.
    for _ in range(3):
        if _alive(conn):
            break
        pool.putconn(conn, close=True)
        conn = pool.getconn()
    broken = False
    try:
        yield conn
    except Exception as e:
        broken = isinstance(e, (psycopg2.OperationalError, psycopg2.InterfaceError))
        if not broken:
            try:
                conn.rollback()
            except Exception as rb_err:
                broken = True
                logger.error("DB rollback failed: {}", rb_err)
        raise
    finally:
        broken = broken or bool(conn.closed)
        if broken:
            _last_used.pop(id(conn), None)
        else:
            _last_used[id(conn)] = time.monotonic()
        pool.putconn(conn, close=broken)

