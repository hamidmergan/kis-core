"""The ring counts the last answer per card, regardless of when it came."""

import os
import uuid as uuid_modul

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from src.features.ai_assistant.repository import exercises as repo  # noqa: E402

# Every tool that records answers.
WERKZEUGE = ("karteikarten", "quiz", "flashcards", "grammatik")
# Exactly the sizes offered in the create dialog.
GROESSEN = (5, 10, 15)

NUTZER = -4242  # gehoert niemandem, die Tabelle hat keinen Fremdschluessel darauf


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
    kennung = f"test-ring-{uuid_modul.uuid4()}"
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO aia_workspaces (uuid, user_id, title) "
                "VALUES (%s, %s, %s) RETURNING id",
                (kennung, NUTZER, "Testraum Fortschrittsring"),
            )
            workspace_id = cur.fetchone()[0]
        conn.commit()
    yield workspace_id
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_workspaces WHERE id = %s", (workspace_id,))
        conn.commit()


def _satz_anlegen(verbindung, workspace_id: int, werkzeug: str, anzahl: int):
    """A finished set with ``anzahl`` cards, returns (set_id, card_ids)."""
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_exercise_sets
                   (workspace_id, user_id, tool, title, mode, card_count, status)
                   VALUES (%s, %s, %s, %s, 'source', %s, 'ready') RETURNING id""",
                (workspace_id, NUTZER, werkzeug, f"Test {werkzeug} {anzahl}", anzahl),
            )
            satz_id = cur.fetchone()[0]
            karten = []
            for i in range(anzahl):
                cur.execute(
                    "INSERT INTO aia_exercise_items (set_id, position, front, back) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    (satz_id, i, f"Frage {i}", f"Antwort {i}"),
                )
                karten.append(cur.fetchone()[0])
        conn.commit()
    return satz_id, karten


def _antworten(verbindung, satz_id: int, karte_id: int, richtig: bool, minuten: int):
    """One answer, ``minuten`` minutes in the past."""
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_exercise_progress
                   (set_id, item_id, user_id, correct, answered_at)
                   VALUES (%s, %s, %s, %s, NOW() - (%s || ' minutes')::interval)""",
                (satz_id, karte_id, NUTZER, richtig, minuten),
            )
        conn.commit()


def _ring(workspace_id: int, satz_id: int) -> int:
    """The percentage the overview paints on the card."""
    saetze = repo.get_exercise_sets(workspace_id, NUTZER)
    zeile = next(s for s in saetze if s["id"] == satz_id)
    return int(zeile["progress_pct"])


@pytest.mark.parametrize("werkzeug", WERKZEUGE)
@pytest.mark.parametrize("anzahl", GROESSEN)
def test_eine_falsche_karte_zieht_genau_ihren_anteil_ab(
    verbindung, arbeitsraum, werkzeug, anzahl,
):
    """All but one correct: with five cards that is 80 percent."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, werkzeug, anzahl)
    for i, karte in enumerate(karten):
        _antworten(verbindung, satz_id, karte, richtig=(i > 0), minuten=anzahl - i)

    assert _ring(arbeitsraum, satz_id) == round((anzahl - 1) / anzahl * 100)


@pytest.mark.parametrize("werkzeug", WERKZEUGE)
@pytest.mark.parametrize("anzahl", GROESSEN)
def test_unterbrochene_uebung_behaelt_ihre_richtigen_karten(
    verbindung, arbeitsraum, werkzeug, anzahl,
):
    """The reported case: two cards first, a pause, then the rest."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, werkzeug, anzahl)
    _antworten(verbindung, satz_id, karten[0], richtig=True, minuten=600)
    _antworten(verbindung, satz_id, karten[1], richtig=True, minuten=595)
    for i, karte in enumerate(karten[2:]):
        _antworten(verbindung, satz_id, karte, richtig=(i > 0), minuten=10 - i)

    assert _ring(arbeitsraum, satz_id) == round((anzahl - 1) / anzahl * 100)


@pytest.mark.parametrize("werkzeug", WERKZEUGE)
@pytest.mark.parametrize("anzahl", GROESSEN)
def test_die_letzte_antwort_einer_karte_gilt(verbindung, arbeitsraum, werkzeug, anzahl):
    """Getting a card wrong later means it can no longer count as learned."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, werkzeug, anzahl)
    for karte in karten:
        _antworten(verbindung, satz_id, karte, richtig=True, minuten=60)
    _antworten(verbindung, satz_id, karten[0], richtig=False, minuten=5)

    assert _ring(arbeitsraum, satz_id) == round((anzahl - 1) / anzahl * 100)


@pytest.mark.parametrize("werkzeug", WERKZEUGE)
@pytest.mark.parametrize("anzahl", GROESSEN)
def test_falsch_und_dann_richtig_zaehlt_als_gesessen(
    verbindung, arbeitsraum, werkzeug, anzahl,
):
    """The second attempt is the point of practising: it has to fill the ring."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, werkzeug, anzahl)
    for karte in karten:
        _antworten(verbindung, satz_id, karte, richtig=False, minuten=60)
    for karte in karten:
        _antworten(verbindung, satz_id, karte, richtig=True, minuten=5)

    assert _ring(arbeitsraum, satz_id) == 100


@pytest.mark.parametrize("werkzeug", WERKZEUGE)
@pytest.mark.parametrize("anzahl", GROESSEN)
def test_halb_bearbeitet_zeigt_die_haelfte(verbindung, arbeitsraum, werkzeug, anzahl):
    """Unanswered cards are not learned, so they do not count either."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, werkzeug, anzahl)
    haelfte = anzahl // 2
    for karte in karten[:haelfte]:
        _antworten(verbindung, satz_id, karte, richtig=True, minuten=5)

    assert _ring(arbeitsraum, satz_id) == round(haelfte / anzahl * 100)


@pytest.mark.parametrize("werkzeug", WERKZEUGE)
def test_ohne_antwort_bleibt_der_ring_leer(verbindung, arbeitsraum, werkzeug):
    satz_id, _ = _satz_anlegen(verbindung, arbeitsraum, werkzeug, 5)
    assert _ring(arbeitsraum, satz_id) == 0


def test_keine_laufmarke_mehr_in_der_antwort(verbindung, arbeitsraum):
    """No field left that hangs off a time window."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, "quiz", 5)
    _antworten(verbindung, satz_id, karten[0], richtig=True, minuten=5)
    zeile = next(
        s for s in repo.get_exercise_sets(arbeitsraum, NUTZER) if s["id"] == satz_id
    )
    assert "last_run_correct" not in zeile
    assert "last_run_start" not in zeile
