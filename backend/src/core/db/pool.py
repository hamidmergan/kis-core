import os
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


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        dsn = os.environ["DATABASE_URL"]
        # The ceiling must be above REQUEST_THREAD_LIMIT, see limits.py.
        _pool = psycopg2.pool.ThreadedConnectionPool(1, DB_POOL_MAX_CONNECTIONS, dsn)
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
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception as rb_err:
            logger.error("DB rollback failed: {}", rb_err)
        raise
    finally:
        pool.putconn(conn)

