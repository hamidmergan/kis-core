"""Der Ring auf der Uebungskarte zeigt, wie viel von einem Satz gerade sitzt.

Gemeldet wurde eine Uebung mit fuenf Karten: vier Antworten richtig, der Ring
zeigte 40 Prozent. Der Grund war die Zaehlweise. Gezaehlt wurden nur Antworten
nach einem Zeitstempel, den der Browser beim ersten Antworten setzte. Wer eine
Uebung unterbrach und danach weitermachte, setzte diesen Zeitstempel mitten im
Durchgang neu und verlor damit alles, was vorher richtig war.

Hier steht die Regel, die stattdessen gilt und die fuer jedes Werkzeug in jeder
waehlbaren Groesse geprueft wird: pro Karte zaehlt die letzte Antwort. Wann
geantwortet wurde, spielt keine Rolle mehr.

Die Regel steckt in SQL, deshalb laeuft der Test gegen echtes Postgres und wird
uebersprungen, wo keins erreichbar ist.
"""

import os
import uuid as uuid_modul

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from src.features.ai_assistant.repository import exercises as repo  # noqa: E402

# Jedes Werkzeug, das Antworten mitschreibt. Mindmap und Datentabelle haben
# keinen Ring, weil man sie nicht beantwortet.
WERKZEUGE = ("karteikarten", "quiz", "flashcards", "grammatik")
# Genau die Groessen, die im Anlegen-Dialog zur Wahl stehen.
GROESSEN = (5, 10, 15)

NUTZER = -4242  # gehoert niemandem, die Tabelle hat keinen Fremdschluessel darauf


@pytest.fixture(scope="module")
def verbindung():
    """Eine Datenbankverbindung oder ein sauberes Ueberspringen."""
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
    """Ein Wegwerf-Workspace. Beim Aufraeumen faellt alles Angehaengte mit."""
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
    """Fertiger Satz mit ``anzahl`` Karten. Liefert (satz_id, karten_ids)."""
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
    """Eine Antwort, ``minuten`` Minuten in der Vergangenheit."""
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
    """Der Prozentwert, den die Uebersicht auf die Karte malt."""
    saetze = repo.get_exercise_sets(workspace_id, NUTZER)
    zeile = next(s for s in saetze if s["id"] == satz_id)
    return int(zeile["progress_pct"])


@pytest.mark.parametrize("werkzeug", WERKZEUGE)
@pytest.mark.parametrize("anzahl", GROESSEN)
def test_eine_falsche_karte_zieht_genau_ihren_anteil_ab(
    verbindung, arbeitsraum, werkzeug, anzahl,
):
    """Alle bis auf eine richtig: bei fuenf Karten sind das 80 Prozent."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, werkzeug, anzahl)
    for i, karte in enumerate(karten):
        _antworten(verbindung, satz_id, karte, richtig=(i > 0), minuten=anzahl - i)

    assert _ring(arbeitsraum, satz_id) == round((anzahl - 1) / anzahl * 100)


@pytest.mark.parametrize("werkzeug", WERKZEUGE)
@pytest.mark.parametrize("anzahl", GROESSEN)
def test_unterbrochene_uebung_behaelt_ihre_richtigen_karten(
    verbindung, arbeitsraum, werkzeug, anzahl,
):
    """Der gemeldete Fall: erst zwei Karten, Stunden Pause, dann der Rest.

    Frueher fiel alles vor der Pause weg, weil der Browser die Laufmarke erst
    beim Weitermachen setzte. Der Ring zeigte dann weniger, als der Lernende
    richtig hatte.
    """
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, werkzeug, anzahl)
    _antworten(verbindung, satz_id, karten[0], richtig=True, minuten=600)
    _antworten(verbindung, satz_id, karten[1], richtig=True, minuten=595)
    for i, karte in enumerate(karten[2:]):
        _antworten(verbindung, satz_id, karte, richtig=(i > 0), minuten=10 - i)

    assert _ring(arbeitsraum, satz_id) == round((anzahl - 1) / anzahl * 100)


@pytest.mark.parametrize("werkzeug", WERKZEUGE)
@pytest.mark.parametrize("anzahl", GROESSEN)
def test_die_letzte_antwort_einer_karte_gilt(verbindung, arbeitsraum, werkzeug, anzahl):
    """Wer eine Karte spaeter falsch hat, kann sie nicht mehr als sitzend zaehlen."""
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
    """Der zweite Anlauf ist der Sinn der Uebung: er muss den Ring fuellen."""
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, werkzeug, anzahl)
    for karte in karten:
        _antworten(verbindung, satz_id, karte, richtig=False, minuten=60)
    for karte in karten:
        _antworten(verbindung, satz_id, karte, richtig=True, minuten=5)

    assert _ring(arbeitsraum, satz_id) == 100


@pytest.mark.parametrize("werkzeug", WERKZEUGE)
@pytest.mark.parametrize("anzahl", GROESSEN)
def test_halb_bearbeitet_zeigt_die_haelfte(verbindung, arbeitsraum, werkzeug, anzahl):
    """Unbeantwortete Karten sitzen nicht, sie zaehlen also auch nicht mit."""
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
    """Die Uebersicht darf kein Feld mehr liefern, das an einem Zeitfenster haengt.

    Solange es da ist, greift die Oberflaeche danach und der gemeldete Fehler
    kommt zurueck.
    """
    satz_id, karten = _satz_anlegen(verbindung, arbeitsraum, "quiz", 5)
    _antworten(verbindung, satz_id, karten[0], richtig=True, minuten=5)
    zeile = next(
        s for s in repo.get_exercise_sets(arbeitsraum, NUTZER) if s["id"] == satz_id
    )
    assert "last_run_correct" not in zeile
    assert "last_run_start" not in zeile
