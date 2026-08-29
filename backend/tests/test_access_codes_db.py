"""Deleting a code must never take an account with it, this checks the real schema."""

import os
import uuid as uuid_modul
from datetime import datetime, timedelta

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from src.features.access_codes import repository as repo  # noqa: E402


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
    except Exception as fehler:  # pragma: no cover - nur ausserhalb des Stacks
        pytest.skip(f"Datenbank nicht erreichbar: {fehler}")
    return get_connection


@pytest.fixture
def schema(verbindung):
    """The tables as init_db builds them, this is what the promise rests on."""
    from src.core.db.schema import init_db
    init_db()
    return verbindung


@pytest.fixture
def konto_am_code(schema):
    """A code plus an account created by it, both disappear afterwards."""
    kennung = uuid_modul.uuid4().hex[:8]
    code_id = repo.create_code(
        code=f"KIS-TEST-{kennung.upper()}",
        label="Testrunde Loeschen",
        role="user",
        custom_role_id=None,
        max_uses=5,
        valid_until=datetime.now() + timedelta(days=30),
        access_days=14,
        created_by=0,
    )
    with schema() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (ldap_username, display_name, email, active, role) "
                "VALUES (%s, %s, %s, 1, 'user') RETURNING id",
                (f"test.loeschen.{kennung}", "Test Loeschen",
                 f"test.loeschen.{kennung}@demo.kis.local"),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
    frist = datetime.now() + timedelta(days=14)
    repo.set_user_access(user_id, expires_at=frist, code_id=code_id)
    yield code_id, user_id, frist
    with schema() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            cur.execute("DELETE FROM access_codes WHERE id = %s", (code_id,))
        conn.commit()


def test_deleting_the_code_keeps_the_account_and_its_deadline(schema, konto_am_code):
    code_id, user_id, frist = konto_am_code

    assert repo.delete_code(code_id) is True

    with schema() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT active, access_expires_at, access_code_id FROM users WHERE id = %s",
                (user_id,),
            )
            zeile = cur.fetchone()

    assert zeile is not None, "Das Konto darf mit dem Code nicht verschwinden"
    aktiv, ablauf, verweis = zeile
    assert aktiv == 1, "Das Konto bleibt eingeschaltet"
    assert verweis is None, "Der Verweis wird geleert, ON DELETE SET NULL"
    assert abs((ablauf - frist).total_seconds()) < 1, "Die Frist steht unveraendert"
