"""Die Datenbankseite des Vorrats.

Geschrieben, weil genau diese Schicht heute schon einmal einen fehlenden ``commit``
durchgelassen hat: die Fachtests mocken sie weg, und ein einzelner Aufruf sieht ohne
Commit richtig aus. Auffallen wuerde es erst beim zweiten.
"""

import json

import pytest

from src.features.ai_assistant.repository import exercise_pool as repo


class _FakeCursor:
    def __init__(self, rows, calls):
        self._rows = list(rows)
        self._calls = calls
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        # Ungekuerzt: die Tests unten pruefen Bestandteile der Anweisung, ein Abschneiden
        # wuerde sie stillschweigend gruen machen.
        self._calls.append(("execute", " ".join(sql.split()), params))
        self.rowcount = 3

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, rows, calls):
        self._rows = rows
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._rows, self._calls)

    def commit(self):
        self._calls.append(("commit", None, None))


@pytest.fixture
def fake_db(monkeypatch):
    def _apply(rows=()):
        calls: list[tuple] = []
        monkeypatch.setattr(repo, "get_connection", lambda: _FakeConn(rows, calls))
        return calls
    return _apply


def _art(*fingerprints):
    return [{"front": f, "back": f.upper()} for f in fingerprints], list(fingerprints)


# --- schreiben committen -------------------------------------------------------

def test_storing_items_commits(fake_db):
    calls = fake_db(rows=[(1,), (2,)])
    items, fps = _art("a", "b")
    repo.add_pool_items(9, "quiz", None, items, fps)
    assert ("commit", None, None) in calls, "ohne commit sieht der naechste Aufruf nichts"


def test_clearing_the_pool_commits(fake_db):
    calls = fake_db()
    repo.clear_pool_for_source(9)
    assert [c[0] for c in calls].count("commit") >= 1


def test_writing_back_the_content_commits(fake_db):
    calls = fake_db()
    repo.materialize_pool_items(9)
    assert ("commit", None, None) in calls


# --- einlagern -----------------------------------------------------------------

def test_an_item_without_a_fingerprint_is_skipped(fake_db):
    fake_db(rows=[(1,)])
    items = [{"front": ""}, {"front": "b"}]
    ids = repo.add_pool_items(9, "quiz", None, items, ["", "b"])
    assert ids[0] is None


def test_a_duplicate_returns_the_id_of_the_row_that_is_already_there(fake_db):
    # ON CONFLICT DO NOTHING liefert keine Zeile zurueck, dann wird die vorhandene
    # gesucht. So kann ein Satz auf eine Aufgabe zeigen, die jemand anderes erzeugt hat.
    calls = fake_db(rows=[None, (42,)])
    items, fps = _art("a")
    assert repo.add_pool_items(9, "quiz", None, items, fps) == [42]
    anweisungen = [c[1] for c in calls if c[0] == "execute"]
    assert any("INSERT" in a for a in anweisungen)
    assert any("SELECT id" in a for a in anweisungen)


def test_json_fields_are_serialised(fake_db):
    calls = fake_db(rows=[(1,)])
    items = [{"front": "a", "back": "A", "options": ["x", "y"], "sources": [{"p": 1}]}]
    repo.add_pool_items(9, "quiz", "B1", items, ["a"])
    params = next(c[2] for c in calls if c[0] == "execute")
    assert params[:5] == (9, "quiz", "B1", None, None)  # ohne Thema, kind ist auch None
    assert params[5] == "a"                              # fingerprint
    assert json.loads(params[9]) == ["x", "y"]          # options


def test_storing_nothing_touches_no_connection(monkeypatch):
    def boom():
        raise AssertionError("es gibt nichts einzulagern")

    monkeypatch.setattr(repo, "get_connection", boom)
    assert repo.add_pool_items(9, "quiz", None, [], []) == []


# --- lesen ---------------------------------------------------------------------

def test_taking_nothing_touches_no_connection(monkeypatch):
    def boom():
        raise AssertionError("es wurde nichts angefordert")

    monkeypatch.setattr(repo, "get_connection", boom)
    assert repo.take_from_pool(9, "quiz", None, 1, 0) == []


def test_the_take_is_random_and_excludes_what_the_person_had(fake_db):
    calls = fake_db(rows=[])
    repo.take_from_pool(9, "quiz", "B1", 3, 5)
    sql = next(c[1] for c in calls if c[0] == "execute")
    assert "random()" in sql, "der Reihe nach zu ziehen liesse den Rest liegen"


def test_the_take_leaves_out_what_the_order_already_holds(fake_db):
    """Die Abfrage kennt nur gespeicherte Saetze, und der entsteht erst am Ende.

    Was ein frueherer Griff in denselben Vorrat schon geholt hat, muss sie deshalb
    gesagt bekommen, sonst liefert sie es ein zweites Mal.
    """
    calls = fake_db(rows=[])
    repo.take_from_pool(9, "quiz", None, 3, 5, exclude_ids=[11, 12])
    sql, params = next((c[1], c[2]) for c in calls if c[0] == "execute")
    assert "p.id <> ALL" in sql
    assert [11, 12] in params


def test_without_an_exclusion_the_take_stays_as_it_was(fake_db):
    calls = fake_db(rows=[])
    repo.take_from_pool(9, "quiz", None, 3, 5)
    sql = next(c[1] for c in calls if c[0] == "execute")
    assert "p.id <> ALL" not in sql


def test_the_level_free_pool_is_matched_with_coalesce(fake_db):
    # Zwei NULL gelten in Postgres nicht als gleich, ein blosses `level = %s` wuerde
    # den niveaulosen Vorrat also nie treffen.
    calls = fake_db(rows=[])
    repo.take_from_pool(9, "quiz", None, 3, 5)
    sql = " ".join(c[1] for c in calls if c[0] == "execute")
    assert "COALESCE" in sql


def test_the_size_is_read_per_pool(fake_db):
    fake_db(rows=[(7,)])
    assert repo.pool_size(9, "quiz", "B1") == 7


def test_seen_fingerprints_reads_by_user_and_tool(fake_db):
    calls = fake_db(rows=[("a",), ("b",)])
    assert repo.seen_fingerprints(3, "quiz") == ["a", "b"]
    params = next(c[2] for c in calls if c[0] == "execute")
    assert params[0] == 3 and params[1] == "quiz"


# --- aufraeumen ----------------------------------------------------------------

def test_clearing_writes_the_content_back_before_deleting(fake_db):
    """Sonst wird ein fertiger Satz leer, weil jemand die Quelle ausgetauscht hat."""
    calls = fake_db()
    repo.clear_pool_for_source(9)
    anweisungen = [c[1] for c in calls if c[0] == "execute"]
    assert anweisungen[0].startswith("UPDATE aia_exercise_items"), \
        "erst zurueckschreiben, dann loeschen"
    assert any("DELETE FROM aia_exercise_pool" in a for a in anweisungen)


# --- die Darreichungsform ------------------------------------------------------

def test_the_kind_of_a_grammar_item_is_stored(fake_db):
    """Ohne die Art kann der Vorrat eine Formatauswahl nicht bedienen: er wuesste
    nicht, was er da liegen hat."""
    calls = fake_db(rows=[(5,)])
    repo.add_pool_items(
        9, "grammatik", "B1",
        [{"front": "f", "back": "b", "_kind": "cloze"}], ["fp"], 4)

    sql, params = calls[0][1], calls[0][2]
    assert "kind" in sql
    # Auf der Position geprueft und nicht nur auf Vorkommen: die Werte haengen an der
    # Reihenfolge der Spaltenliste, und ein Verrutschen wuerde die Art still in die
    # Nachbarspalte schreiben.
    assert params[4] == "cloze"


def test_an_item_without_a_kind_stores_null(fake_db):
    """Jedes andere Werkzeug hat keine Arten. Die Spalte bleibt dort leer."""
    calls = fake_db(rows=[(5,)])
    repo.add_pool_items(9, "quiz", None, [{"front": "f", "back": "b"}], ["fp"])

    assert calls[0][2][4] is None


def test_a_format_choice_narrows_the_take(fake_db):
    calls = fake_db()
    repo.take_from_pool(9, "grammatik", None, 3, 5, 4, kinds=["transform", "cloze"])

    sql, params = calls[0][1], calls[0][2]
    assert "p.kind = ANY(%s)" in sql
    assert ["transform", "cloze"] in params


def test_without_a_format_choice_the_take_stays_as_it_was(fake_db):
    """Gemischt holt alles, auch Altbestand ohne Art. Sonst waere der ganze
    bestehende Vorrat mit einem Schlag wertlos."""
    calls = fake_db()
    repo.take_from_pool(9, "quiz", None, 3, 5)

    assert "p.kind" not in calls[0][1]


def test_the_exclusion_and_the_format_choice_keep_their_order(fake_db):
    """Beide haengen einen Platzhalter an dieselbe Anweisung. Laufen Text und Werte
    auseinander, sucht die Abfrage stillschweigend nach dem Falschen."""
    calls = fake_db()
    repo.take_from_pool(9, "grammatik", None, 3, 5, 4,
                        exclude_ids=[11], kinds=["cloze"])

    params = calls[0][2]
    assert list(params).index([11]) < list(params).index(["cloze"])
