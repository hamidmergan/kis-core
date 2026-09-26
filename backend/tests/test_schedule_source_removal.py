"""Deleting a source takes its hits off the schedule, entries it alone found go with it."""

import os
import uuid as uuid_modul
from datetime import date

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from src.features.ai_assistant.repository import schedule as repo  # noqa: E402

NUTZER = -4244  # gehoert niemandem, die Tabelle hat keinen Fremdschluessel darauf
WEG = "quelle-weg"
BLEIBT = "quelle-bleibt"


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
def arbeitsraum(verbindung):
    """A throwaway workspace, cleanup takes everything attached with it."""
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO aia_workspaces (uuid, user_id, title) VALUES (%s, %s, %s) RETURNING id",
                (f"test-zeitplan-{uuid_modul.uuid4()}", NUTZER, "Testraum Zeitplan"),
            )
            workspace_id = cur.fetchone()[0]
        conn.commit()
    yield workspace_id
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_workspaces WHERE id = %s", (workspace_id,))
        conn.commit()


def _ref(source_uuid, seite=1):
    return {"source_uuid": source_uuid, "page_number": seite, "start_time": None, "raw_quote": "x"}


def _eintrag(workspace_id, titel, refs, origin="llm", user_id=NUTZER):
    return repo.create_schedule_entry(
        workspace_id, user_id, type="termin", title=titel, description=None,
        due_date=date(2027, 1, 10), due_time=None, is_optional=False,
        origin=origin, source_refs=refs,
    )["id"]


def _refs(verbindung, entry_id):
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT source_refs FROM aia_schedule_entries WHERE id = %s", (entry_id,))
            row = cur.fetchone()
    return None if row is None else row[0]


def test_eintrag_nur_aus_der_quelle_verschwindet(verbindung, arbeitsraum):
    nur = _eintrag(arbeitsraum, "Klausur", [_ref(WEG), _ref(WEG, 2)])

    assert repo.remove_source_from_schedule(arbeitsraum, WEG) == (1, 0)
    assert _refs(verbindung, nur) is None


def test_eintrag_mit_zweiter_quelle_bleibt_ohne_ihren_chip(verbindung, arbeitsraum):
    beide = _eintrag(arbeitsraum, "Abgabe", [_ref(WEG), _ref(BLEIBT)])

    assert repo.remove_source_from_schedule(arbeitsraum, WEG) == (0, 1)
    assert [r["source_uuid"] for r in _refs(verbindung, beide)] == [BLEIBT]


def test_andere_quellen_und_eigene_eintraege_bleiben_unberuehrt(verbindung, arbeitsraum):
    fremd = _eintrag(arbeitsraum, "Sprechstunde", [_ref(BLEIBT)])
    haendisch = _eintrag(arbeitsraum, "Lerngruppe", [], origin="manual")

    assert repo.remove_source_from_schedule(arbeitsraum, WEG) == (0, 0)
    assert _refs(verbindung, fremd) == [_ref(BLEIBT)]
    assert _refs(verbindung, haendisch) == []


def test_gilt_fuer_alle_personen_im_workspace(verbindung, arbeitsraum):
    mein = _eintrag(arbeitsraum, "Klausur", [_ref(WEG)])
    dein = _eintrag(arbeitsraum, "Klausur", [_ref(WEG)], user_id=NUTZER - 1)

    assert repo.remove_source_from_schedule(arbeitsraum, WEG) == (2, 0)
    assert _refs(verbindung, mein) is None and _refs(verbindung, dein) is None


def test_andere_workspaces_bleiben_stehen(verbindung, arbeitsraum):
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO aia_workspaces (uuid, user_id, title) VALUES (%s, %s, %s) RETURNING id",
                (f"test-zeitplan-{uuid_modul.uuid4()}", NUTZER, "Nachbar"),
            )
            nachbar = cur.fetchone()[0]
        conn.commit()
    try:
        drueben = _eintrag(nachbar, "Klausur", [_ref(WEG)])
        assert repo.remove_source_from_schedule(arbeitsraum, WEG) == (0, 0)
        assert _refs(verbindung, drueben) == [_ref(WEG)]
    finally:
        with verbindung() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM aia_workspaces WHERE id = %s", (nachbar,))
            conn.commit()


def test_geschriebenes_jahr_beendet_die_annahme(verbindung, arbeitsraum):
    eid = repo.create_schedule_entry(
        arbeitsraum, NUTZER, type="termin", title="Klausur", description=None,
        due_date=date(2027, 1, 10), due_time=None, is_optional=False,
        origin="llm", source_refs=[_ref(WEG)], year_assumed=True,
    )["id"]
    repo.append_source_ref_to_entry(eid, _ref(BLEIBT), year_written=False)
    assert repo.get_schedule_entry(eid, NUTZER)["year_assumed"] is True
    repo.append_source_ref_to_entry(eid, _ref(BLEIBT, 3), year_written=True)
    assert repo.get_schedule_entry(eid, NUTZER)["year_assumed"] is False
