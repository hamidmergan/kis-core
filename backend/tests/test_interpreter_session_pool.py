"""The pool of conversations: the last 100 stay, the one untouched longest drops out."""

import os

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from src.features.interpreter import repository as repo  # noqa: E402
from src.limits import MAX_INTERPRETER_SESSIONS  # noqa: E402


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
def eigentuemer(verbindung):
    """An owner id nobody else uses, with every conversation of it gone afterwards."""
    from src.core.db.schema import init_db
    init_db()
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(owner_id), 0) + 1 FROM interpreter_sessions")
            owner_id = cur.fetchone()[0] + 900_000
    yield owner_id
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM interpreter_sessions WHERE owner_id = %s", (owner_id,))
        conn.commit()


def _anlegen(owner_id: int, name: str) -> str:
    return repo.create_session(owner_id, "DE", "EN-US", name, "Gast")["id"]


def _beruehren(verbindung, session_id: str, minuten_alt: int) -> None:
    """Sets how long ago a conversation was last used, the pool sorts by that."""
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE interpreter_sessions SET updated_at = NOW() - make_interval(mins => %s) WHERE id = %s",
                (minuten_alt, session_id),
            )
        conn.commit()


def test_unter_der_grenze_bleibt_alles_liegen(eigentuemer):
    ids = [_anlegen(eigentuemer, f"P{n}") for n in range(3)]
    gespeichert = {row["id"] for row in repo.list_sessions(eigentuemer)}
    assert gespeichert == set(ids)


def test_an_der_grenze_faellt_das_am_laengsten_unbenutzte_heraus(verbindung, eigentuemer):
    """The pool is filled to the brim, then one more conversation starts."""
    ids = [_anlegen(eigentuemer, f"P{n}") for n in range(MAX_INTERPRETER_SESSIONS)]
    for abstand, session_id in enumerate(ids):
        _beruehren(verbindung, session_id, MAX_INTERPRETER_SESSIONS - abstand)
    aeltestes = ids[0]

    neues = _anlegen(eigentuemer, "das neue")

    gespeichert = [row["id"] for row in repo.list_sessions(eigentuemer)]
    assert len(gespeichert) == MAX_INTERPRETER_SESSIONS
    assert aeltestes not in gespeichert, "das am längsten unbenutzte Gespräch muss weichen"
    assert neues in gespeichert
    assert repo.get_session(aeltestes) is None, "es ist wirklich weg, nicht nur unsichtbar"


def test_ein_wieder_geoeffnetes_gespraech_rutscht_nach_oben(verbindung, eigentuemer):
    """Whoever carries on an old conversation keeps it, the next one in line goes instead."""
    ids = [_anlegen(eigentuemer, f"P{n}") for n in range(MAX_INTERPRETER_SESSIONS)]
    for abstand, session_id in enumerate(ids):
        _beruehren(verbindung, session_id, MAX_INTERPRETER_SESSIONS - abstand)
    repo.update_session(ids[0])  # touched again, updated_at is now

    _anlegen(eigentuemer, "das neue")

    gespeichert = [row["id"] for row in repo.list_sessions(eigentuemer)]
    assert ids[0] in gespeichert, "das fortgeführte Gespräch bleibt"
    assert ids[1] not in gespeichert, "dafür geht das nächstälteste"


def test_fremde_gespraeche_bleiben_unberuehrt(verbindung, eigentuemer):
    fremd = eigentuemer + 1
    try:
        fremdes = _anlegen(fremd, "nicht meins")
        for n in range(MAX_INTERPRETER_SESSIONS + 5):
            _anlegen(eigentuemer, f"P{n}")
        assert repo.get_session(fremdes) is not None
    finally:
        with verbindung() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM interpreter_sessions WHERE owner_id = %s", (fremd,))
            conn.commit()


def test_die_saetze_des_verdraengten_gespraechs_gehen_mit(verbindung, eigentuemer):
    """Without the cascade the turns would sit in the table forever with nothing pointing at them."""
    opfer = _anlegen(eigentuemer, "wird verdrängt")
    repo.upsert_turn(opfer, {
        "id": "t-opfer", "side": "left", "source": "typed", "original": "Guten Tag",
        "translation": "Good day", "status": "done", "edited": False, "at": 1,
    })
    _beruehren(verbindung, opfer, 10_000)
    for n in range(MAX_INTERPRETER_SESSIONS):
        _anlegen(eigentuemer, f"P{n}")

    assert repo.get_session(opfer) is None
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM interpreter_turns WHERE session_id = %s", (opfer,))
            assert cur.fetchone()[0] == 0
