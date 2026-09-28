"""Der Start baut den Vektor-Index von aia_chunks nicht mehr jedes Mal neu.

Gefunden 28.09.2026: init_db stellte die Spalte embedding bei jedem Start auf vector um. Das baut den
HNSW-Index neu, lokal mit 80.000 Abschnitten dauerte das Minuten und sperrte die Tabelle.
Jetzt nur noch, wenn die Spalte noch eine feste Dimension hat.
"""
import os
import uuid

import pytest


@pytest.fixture(scope="module")
def verbindung():
    """A database connection or a clean skip."""
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("kein DATABASE_URL gesetzt (Test braucht echtes Postgres)")
    from src.core.db.pool import get_connection
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as fehler:  # pragma: no cover - only outside the stack
        pytest.skip(f"Datenbank nicht erreichbar: {fehler}")
    return get_connection


@pytest.fixture
def wegwerf_schema(verbindung):
    """A throwaway schema inside a transaction that is rolled back, the real aia_chunks stays untouched."""
    with verbindung() as conn:
        try:
            with conn.cursor() as cur:
                name = f"test_vektor_{uuid.uuid4().hex[:8]}"
                cur.execute(f"CREATE SCHEMA {name}")
                cur.execute(f"SET LOCAL search_path TO {name}, public")
                yield cur
        finally:
            conn.rollback()


def _typ(cur) -> str:
    cur.execute("""SELECT format_type(atttypid, atttypmod) FROM pg_attribute
                   WHERE attrelid = 'aia_chunks'::regclass AND attname = 'embedding'""")
    return cur.fetchone()[0]


def _index_oid(cur) -> int:
    cur.execute("SELECT 'idx_test_embedding'::regclass::oid")
    return cur.fetchone()[0]


def test_eine_feste_dimension_wird_einmal_entfernt(wegwerf_schema):
    from src.core.db import schema as schema_mod

    cur = wegwerf_schema
    cur.execute("CREATE TABLE aia_chunks (id SERIAL PRIMARY KEY, embedding vector(3))")

    assert schema_mod._drop_embedding_dimension_once(cur) is True
    assert _typ(cur) == "vector"
    assert schema_mod._drop_embedding_dimension_once(cur) is False


def test_ohne_feste_dimension_bleibt_der_index_unangetastet(wegwerf_schema):
    """A rebuilt index gets a new identity, an untouched one keeps it."""
    from src.core.db import schema as schema_mod

    cur = wegwerf_schema
    cur.execute("CREATE TABLE aia_chunks (id SERIAL PRIMARY KEY, embedding vector)")
    cur.execute("INSERT INTO aia_chunks (embedding) VALUES ('[1,2,3]'), ('[3,2,1]')")
    cur.execute("CREATE INDEX idx_test_embedding ON aia_chunks USING hnsw "
                "((embedding::halfvec(3)) halfvec_cosine_ops) WHERE vector_dims(embedding) = 3")
    vorher = _index_oid(cur)

    assert schema_mod._drop_embedding_dimension_once(cur) is False
    assert _index_oid(cur) == vorher


def test_ohne_tabelle_passiert_nichts(wegwerf_schema):
    from src.core.db import schema as schema_mod

    assert schema_mod._drop_embedding_dimension_once(wegwerf_schema) is False
