import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool
from loguru import logger
from psycopg2.extras import RealDictCursor

from src.limits import MAX_RESULT_FILES, JOB_RETENTION_HOURS, DB_POOL_MAX_CONNECTIONS

_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        dsn = os.environ["DATABASE_URL"]
        # Obergrenze muss ueber REQUEST_THREAD_LIMIT liegen, siehe limits.py.
        # Der Vorrat waechst traege, die Zahl reserviert nichts im Voraus.
        _pool = psycopg2.pool.ThreadedConnectionPool(1, DB_POOL_MAX_CONNECTIONS, dsn)
    return _pool


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

