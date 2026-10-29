"""The connection pool keeps idle connections instead of closing each after the request.

Load test 26.09.: psycopg2 keeps only minconn=1 idle, every process opened and closed connections under the pool lock, Postgres ran at 117 % and the backend main thread stalled.
"""

import psycopg2.pool

from src.core.db import pool as db_pool


class _Conn:
    closed = 0

    class info:
        transaction_status = 0

    def close(self):
        self.closed = 1


def _pool_mit(monkeypatch, behalten):
    monkeypatch.setenv("DB_POOL_KEEP_IDLE", str(behalten))
    monkeypatch.setattr(psycopg2.pool.ThreadedConnectionPool, "_connect", lambda self, key=None: _merke(self, _Conn()))
    monkeypatch.setattr(db_pool, "_pool", None)
    return db_pool._get_pool()


def _merke(pool, conn):
    pool._used[id(conn)] = conn
    pool._rused[id(conn)] = id(conn)
    return conn


def test_zurueckgegebene_verbindungen_bleiben_offen(monkeypatch):
    pool = _pool_mit(monkeypatch, 3)
    conns = [pool.getconn() for _ in range(3)]
    for c in conns:
        pool.putconn(c)

    assert not any(c.closed for c in conns)
    assert len(pool._pool) == 3


def test_ueber_der_grenze_wird_geschlossen(monkeypatch):
    pool = _pool_mit(monkeypatch, 2)
    conns = [pool.getconn() for _ in range(4)]
    for c in conns:
        pool.putconn(c)

    assert sum(1 for c in conns if c.closed) == 2
    assert len(pool._pool) == 2
