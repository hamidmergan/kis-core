"""Der Verbindungspool gibt keine toten Verbindungen weiter.

Lasttest 26.09.: Postgres wurde abgeschossen und startete neu. Stunden später scheiterte
der Aufseher immer noch alle paar Takte an "server closed the connection unexpectedly".
"""

import psycopg2
import pytest

from src.core.db import pool as db_pool


class _Conn:
    def __init__(self, closed=0):
        self.closed = closed
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


class _Pool:
    def __init__(self, conns):
        self.conns = list(conns)
        self.zurueck = []

    def getconn(self):
        return self.conns.pop(0)

    def putconn(self, conn, close=False):
        self.zurueck.append((conn, close))


@pytest.fixture
def pool(monkeypatch):
    def mach(*conns):
        p = _Pool(conns)
        monkeypatch.setattr(db_pool, "_get_pool", lambda: p)
        monkeypatch.setattr(db_pool, "_alive", lambda conn: not conn.closed)
        return p
    return mach


def test_eine_verbindung_mit_abgebrochener_leitung_wird_verworfen(pool):
    conn = _Conn()
    p = pool(conn)
    with pytest.raises(psycopg2.OperationalError):
        with db_pool.get_connection():
            raise psycopg2.OperationalError("server closed the connection unexpectedly")
    assert p.zurueck == [(conn, True)]


def test_ein_normaler_fehler_behaelt_die_verbindung(pool):
    conn = _Conn()
    p = pool(conn)
    with pytest.raises(ValueError):
        with db_pool.get_connection():
            raise ValueError("falsche Eingabe")
    assert p.zurueck == [(conn, False)]


def test_eine_tote_verbindung_aus_dem_pool_wird_ersetzt(pool):
    tot, frisch = _Conn(closed=2), _Conn()
    p = pool(tot, frisch)
    with db_pool.get_connection() as conn:
        assert conn is frisch
    assert (tot, True) in p.zurueck


def test_nach_dem_abspalten_eines_arbeiters_beginnt_ein_eigener_pool(monkeypatch):
    """Ein geerbter Pool teilt die Leitung mit dem Elternprozess, und ist sie tot, bleibt sie tot."""
    monkeypatch.setattr(db_pool, "_pool", object())
    db_pool.reset_after_fork()
    assert db_pool._pool is None


def test_jeder_abgespaltene_celery_prozess_setzt_den_pool_zurueck(monkeypatch):
    from celery.signals import worker_process_init
    from src import celery_app  # noqa: F401 - registers the handler
    monkeypatch.setattr(db_pool, "_pool", object())
    worker_process_init.send(sender=None)
    assert db_pool._pool is None
