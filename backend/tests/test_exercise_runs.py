"""Every round counts on its own, the backend assigns the number."""

import os
import uuid as uuid_modul
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from src.features.ai_assistant.repository import exercises as repo  # noqa: E402
from src.features.ai_assistant.repository import stats as stats_repo  # noqa: E402

NUTZER = -4243  # gehoert niemandem, die Tabelle hat keinen Fremdschluessel darauf
BERLIN = ZoneInfo("Europe/Berlin")


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
    kennung = f"test-runs-{uuid_modul.uuid4()}"
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO aia_workspaces (uuid, user_id, title) "
                "VALUES (%s, %s, %s) RETURNING id",
                (kennung, NUTZER, "Testraum Durchgaenge"),
            )
            workspace_id = cur.fetchone()[0]
        conn.commit()
    yield workspace_id
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_workspaces WHERE id = %s", (workspace_id,))
        conn.commit()


def _satz_anlegen(verbindung, workspace_id: int, anzahl: int = 10):
    """A finished set with ``anzahl`` cards, returns (set_id, card_ids)."""
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_exercise_sets
                   (workspace_id, user_id, tool, title, mode, card_count, status)
                   VALUES (%s, %s, 'quiz', %s, 'source', %s, 'ready') RETURNING id""",
                (workspace_id, NUTZER, f"Test Durchgaenge {anzahl}", anzahl),
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


def _nummern(verbindung, satz_id: int) -> list[int]:
    """The round numbers of the answers, in insertion order."""
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT run_no FROM aia_exercise_progress "
                "WHERE set_id = %s ORDER BY id",
                (satz_id,),
            )
            return [zeile[0] for zeile in cur.fetchall()]


def _durchgang_antworten(satz_id: int, karten: list[int], richtige: int, neu: bool = True):
    """One round: the first answer opens it, the rest joins in."""
    for i, karte in enumerate(karten):
        repo.bulk_record_exercise_progress(
            satz_id, NUTZER,
            [{"item_id": karte, "correct": i < richtige}],
            new_run=(neu and i == 0),
        )


def test_erster_durchgang_bekommt_die_eins(verbindung, arbeitsraum):
    """Without a history the counting starts at one."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum)
    _durchgang_antworten(satz_id, karten[:3], richtige=3)

    assert _nummern(verbindung, satz_id) == [1, 1, 1]


def test_zweiter_durchgang_zaehlt_hoch(verbindung, arbeitsraum):
    """Whoever opens the same set again starts round two."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum)
    _durchgang_antworten(satz_id, karten[:2], richtige=2)
    _durchgang_antworten(satz_id, karten[:2], richtige=1)

    assert _nummern(verbindung, satz_id) == [1, 1, 2, 2]


def test_antwort_ohne_meldung_bleibt_im_laufenden_durchgang(verbindung, arbeitsraum):
    """Only the first answer opens the round, all the others belong to it."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum)
    repo.bulk_record_exercise_progress(
        satz_id, NUTZER, [{"item_id": karten[0], "correct": True}], new_run=True,
    )
    repo.bulk_record_exercise_progress(
        satz_id, NUTZER, [{"item_id": karten[1], "correct": False}], new_run=False,
    )

    assert _nummern(verbindung, satz_id) == [1, 1]


def test_verlorene_erste_antwort_erzeugt_keinen_nulldurchgang(verbindung, arbeitsraum):
    """If the first answer never arrived, the second still lands in round one."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum)
    repo.bulk_record_exercise_progress(
        satz_id, NUTZER, [{"item_id": karten[0], "correct": True}], new_run=False,
    )

    assert _nummern(verbindung, satz_id) == [1]


def _antwort_am_tag(verbindung, satz_id: int, karte_id: int, richtig: bool,
                    run_no, stunde: int, minute: int = 0):
    """An answer at a fixed time on the current day."""
    heute = datetime.now(BERLIN).date()
    zeitpunkt = datetime(heute.year, heute.month, heute.day, stunde, minute)
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_exercise_progress
                   (set_id, item_id, user_id, correct, run_no, answered_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (satz_id, karte_id, NUTZER, richtig, run_no, zeitpunkt),
            )
        conn.commit()


def _heute(workspace_id: int) -> dict:
    """The day view for today."""
    heute = str(datetime.now(BERLIN).date())
    return stats_repo.get_student_day_stats(workspace_id, NUTZER, heute)


def test_zwei_durchgaenge_stehen_getrennt(verbindung, arbeitsraum):
    """The wanted case: first 5 of 10, then 7 of 10, no mixed rate."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, anzahl=10)
    for i, karte in enumerate(karten):
        _antwort_am_tag(verbindung, satz_id, karte, i < 5, run_no=1, stunde=8, minute=i)
    for i, karte in enumerate(karten):
        _antwort_am_tag(verbindung, satz_id, karte, i < 7, run_no=2, stunde=9, minute=i)

    satz = next(s for s in _heute(arbeitsraum)["sets"] if s["set_id"] == satz_id)

    assert [(r["run_no"], r["correct"], r["total"]) for r in satz["runs"]] == [
        (1, 5, 10), (2, 7, 10),
    ]


def test_abgebrochener_durchgang_zaehlt_gegen_die_kartenzahl(verbindung, arbeitsraum):
    """Left at exercise three, one and two correct, gives 2 of 10."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, anzahl=10)
    _antwort_am_tag(verbindung, satz_id, karten[0], True, run_no=1, stunde=8)
    _antwort_am_tag(verbindung, satz_id, karten[1], True, run_no=1, stunde=8, minute=1)

    satz = next(s for s in _heute(arbeitsraum)["sets"] if s["set_id"] == satz_id)

    assert [(r["run_no"], r["correct"], r["total"]) for r in satz["runs"]] == [(1, 2, 10)]


def test_alte_antworten_ohne_nummer_sind_ein_durchgang(verbindung, arbeitsraum):
    """Answers from before the column carry no number and collapse together."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, anzahl=10)
    for i, karte in enumerate(karten[:4]):
        _antwort_am_tag(verbindung, satz_id, karte, i < 3, run_no=None, stunde=7, minute=i)

    satz = next(s for s in _heute(arbeitsraum)["sets"] if s["set_id"] == satz_id)

    assert [(r["run_no"], r["correct"], r["total"]) for r in satz["runs"]] == [(None, 3, 10)]


def _antwort_vor_tagen(verbindung, satz_id: int, karte_id: int, richtig: bool,
                       run_no, tage: int):
    """An answer ``tage`` days in the past."""
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_exercise_progress
                   (set_id, item_id, user_id, correct, run_no, answered_at)
                   VALUES (%s, %s, %s, %s, %s, NOW() - (%s || ' days')::interval)""",
                (satz_id, karte_id, NUTZER, richtig, run_no, tage),
            )
        conn.commit()


def _zeilen(verbindung, satz_id: int) -> list[tuple]:
    """What is left: round and verdict per row, in insertion order."""
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT run_no, correct FROM aia_exercise_progress "
                "WHERE set_id = %s ORDER BY item_id, answered_at",
                (satz_id,),
            )
            return [tuple(z) for z in cur.fetchall()]


def test_aufraeumen_behaelt_die_letzte_antwort_je_karte(verbindung, arbeitsraum):
    """Old answers drop out, except the newest per card."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, anzahl=3)
    for nr in (1, 2, 3):
        for karte in karten:
            _antwort_vor_tagen(verbindung, satz_id, karte, richtig=(nr == 3),
                               run_no=nr, tage=400 - nr)

    entfernt = repo.prune_old_exercise_progress()

    assert entfernt >= 6
    assert _zeilen(verbindung, satz_id) == [(3, True), (3, True), (3, True)]


def test_aufraeumen_laesst_die_letzten_sechs_monate_in_ruhe(verbindung, arbeitsraum):
    """Everything inside the window stays complete, several rounds per card included."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, anzahl=2)
    for nr in (1, 2):
        for karte in karten:
            _antwort_vor_tagen(verbindung, satz_id, karte, richtig=True,
                               run_no=nr, tage=100 + nr)

    repo.prune_old_exercise_progress()

    assert len(_zeilen(verbindung, satz_id)) == 4


def test_aufraeumen_laesst_den_ring_unveraendert(verbindung, arbeitsraum):
    """The percentage on the exercise card has to be the same afterwards."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, anzahl=4)
    for nr in (1, 2):
        for i, karte in enumerate(karten):
            # In the second round three of four cards are learned.
            _antwort_vor_tagen(verbindung, satz_id, karte,
                               richtig=(nr == 2 and i > 0), run_no=nr, tage=400 - nr)

    def ring() -> int:
        satz = next(s for s in repo.get_exercise_sets(arbeitsraum, NUTZER) if s["id"] == satz_id)
        return int(satz["progress_pct"])

    vorher = ring()
    repo.prune_old_exercise_progress()

    assert vorher == 75
    assert ring() == 75


def test_durchgaenge_stehen_in_der_reihenfolge_ihres_laufs(verbindung, arbeitsraum):
    """Old before new, so the development reads top to bottom."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, anzahl=10)
    _antwort_am_tag(verbindung, satz_id, karten[0], True, run_no=2, stunde=9)
    _antwort_am_tag(verbindung, satz_id, karten[0], False, run_no=1, stunde=8)
    _antwort_am_tag(verbindung, satz_id, karten[1], True, run_no=None, stunde=7)

    satz = next(s for s in _heute(arbeitsraum)["sets"] if s["set_id"] == satz_id)

    assert [r["run_no"] for r in satz["runs"]] == [None, 1, 2]
