"""Die Beleg-Suche darf nur noch die Seiten ranken, die das Modell gesehen hat.

Warum es das gibt. Die Chips entstehen nach der Antwort: je Satz laeuft eine
Hybrid-Suche, und ``_is_seen`` warf danach in Python alles weg, was nicht auf einer
abgerufenen Seite lag. Die Datenbank rankte also erst den ganzen Workspace (gemessen:
12.130 Chunks in Workspace 4) und Python zerriss die Liste hinterher. Zwei Folgen:
unnoetige Last je Antwortsatz, und ein passender Chunk hinter Platz 40 fiel aus der
Kandidatenliste, bevor der Filter ihn ueberhaupt sah. Das Limit wurde deshalb schon
von 4 auf 10 auf 40 hochgezogen, ein Pflaster.

Der Filter steht jetzt in der WHERE-Klausel. Die Bedeutung ist DIESELBE wie in
``_is_seen``, nur frueher: eine PDF-Quelle nur auf ihren gesehenen Seiten, eine
Medienquelle ganz (eine Zeitmarke hat keine Seite, dort wird je Quelle geprueft).

``_is_seen`` bleibt trotzdem stehen: der woertliche Abgleich und der Zahlen-Nachschlag
laufen nicht durch diese Abfrage und brauchen die Pruefung weiter.

Die FORM des Fragments ist gemessen, nicht Geschmack. Eine Fassung mit
``EXISTS (SELECT 1 FROM unnest(...))`` liest sich kuerzer, laesst sich aber nicht auf
einen Index abbilden: Postgres macht daraus einen Semi-Join und faellt auf den vollen
Durchlauf zurueck (675 ms gemessen). Eine ODER-Kette je Quelle wird zu einem BitmapOr
ueber ``idx_chunks_source_page`` und braucht 6,8 ms. Deshalb steht hier eine Kette.
"""
import time

import pytest

from src.features.ai_assistant.repository import chunks as repo


WS = 4243
_FRAGMENT = "c.source_id = %s"


class _FakeCursor:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((sql, params))

    def fetchall(self):
        return []          # keine Treffer -> die Funktion bricht nach der Fusion ab


class _FakeConn:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._calls)


@pytest.fixture
def abfragen(monkeypatch):
    """Ruft hybrid_search_chunks gegen eine Attrappe und liefert die SQL-Aufrufe."""
    # IDF-Gedaechtnis vorbelegen, damit die Zaehl-Abfragen entfallen und der
    # Stichwortarm trotzdem gebaut wird (er braucht ein Wort mit Gewicht).
    jetzt = time.monotonic()
    monkeypatch.setitem(repo._IDF_N_CACHE, WS, (jetzt, 1000))
    monkeypatch.setitem(repo._IDF_CACHE, (WS, "fragestunde"), (jetzt, 3.0))

    def _lauf(**kwargs):
        calls: list[tuple] = []
        monkeypatch.setattr(repo, "get_connection", lambda: _FakeConn(calls))
        repo.hybrid_search_chunks(WS, "Fragestunde", [0.1] * 2560, **kwargs)
        return [(sql, p) for sql, p in calls if "aia_chunks" in sql]

    return _lauf


def test_ohne_angabe_bleibt_die_abfrage_wie_bisher(abfragen):
    # Der Hauptabruf (Schritt 2 im Chat) sucht weiter ueber den ganzen Workspace.
    # Nur die Beleg-Suche nach der Antwort schraenkt ein.
    for sql, _params in abfragen():
        assert _FRAGMENT not in sql


def test_jeder_arm_der_suche_traegt_den_filter(abfragen):
    # Vektor, Stichwort und Teilstring werden getrennt abgefragt und erst danach
    # per RRF verschmolzen. Traegt nur einer den Filter, holt ein anderer die
    # ungesehenen Seiten wieder herein.
    treffer = [sql for sql, _p in abfragen(seen_pages={7: {5, 6}})
               if _FRAGMENT in sql]
    assert len(treffer) == 3


def test_pdf_quelle_nur_auf_ihren_gesehenen_seiten(abfragen):
    geprueft = 0
    for sql, params in abfragen(seen_pages={7: {6, 5}}):
        if _FRAGMENT not in sql:
            continue
        geprueft += 1
        # Quelle als Einzelwert, Seiten als Liste: genau die Form, die der
        # Bitmap-Index-Scan auf idx_chunks_source_page bedienen kann.
        assert "(c.source_id = %s AND c.page_number = ANY(%s))" in sql
        assert 7 in params
        assert [5, 6] in params
    assert geprueft == 3


def test_medienquelle_kommt_ganz_durch(abfragen):
    # Ton und Video haben eine LEERE Seitenmenge: der Chip zeigt dort auf eine
    # Zeitmarke, nicht auf eine Seite. Die Quelle muss vollstaendig durchkommen,
    # sonst verliert jedes Video seine Belege.
    geprueft = 0
    for sql, params in abfragen(seen_pages={9: set()}):
        if _FRAGMENT not in sql:
            continue
        geprueft += 1
        assert 9 in params
        # Keine Seitenbedingung fuer diese Quelle, sonst faellt jedes Video durch.
        assert "(c.source_id = %s)" in sql
        assert not any(isinstance(p, list) for p in params)
    assert geprueft == 3


def test_quelle_ohne_eintrag_faellt_ganz_weg(abfragen):
    # Eine Quelle, die gar nicht abgerufen wurde, darf keinen Chip bekommen.
    # In _is_seen ist das der Fall "pages is None -> False".
    geprueft = 0
    for sql, params in abfragen(seen_pages={7: {5}}):
        if _FRAGMENT not in sql:
            continue
        geprueft += 1
        assert 8 not in params
    assert geprueft == 3
