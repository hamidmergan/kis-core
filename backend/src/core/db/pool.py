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
def run_once_across_processes(key: int):
    """Gibt genau EINEM Prozess ``True``, allen anderen ``False``.

    Gebraucht für das Anlegen des Schemas beim Start. Mit mehreren
    uvicorn-Prozessen würden sonst alle gleichzeitig ``CREATE EXTENSION`` und
    ``CREATE TABLE IF NOT EXISTS`` ausführen. Das "IF NOT EXISTS" schützt dabei
    nicht: Postgres kann bei echt gleichzeitigem Anlegen mit einem
    Schlüsselkonflikt in seinen Systemtabellen abbrechen, und dann startet ein
    Prozess nicht.

    Warum nicht einfach ein Riegel, hinter dem alle der Reihe nach dasselbe tun:
    das war die erste Fassung und sie war MESSBAR SCHLECHTER. Jeder Prozess hat
    den kompletten Schema-Durchlauf wiederholt, gemessen etwa 30 Sekunden. Bei 8
    Prozessen kamen sie im Abstand von 30 Sekunden hoch, nach zweieinhalb
    Minuten waren erst 5 von 8 bereit. Vorher war der Start nach 35 Sekunden
    fertig.

    Jetzt macht die Arbeit nur der Erste. Die anderen warten, bis er fertig ist,
    und überspringen dann. Warten statt sofort weiterlaufen ist wichtig, sonst
    würde ein Prozess Anfragen annehmen, während das Schema noch halb fertig ist.

    Bewusst ein sitzungsweiter Riegel (``pg_advisory_lock``), kein
    transaktionsweiter: das Schema-Anlegen macht mehrere Commits, ein
    transaktionsweiter Riegel würde nach dem ersten davon aufgehen.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (key,))
            am_first = bool(cur.fetchone()[0])
            conn.commit()   # Transaktion beenden, der Riegel bleibt (sitzungsweit)

            if not am_first:
                # Auf den Ersten warten, dann sofort wieder freigeben und nichts tun.
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
                    # Nicht verschweigen: die Verbindung geht zurück in den
                    # Vorrat, ein haengender Riegel wuerde den naechsten Start
                    # blockieren.
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

