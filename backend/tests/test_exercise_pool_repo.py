"""Checks the database side of the pool, a missing commit would show up late otherwise."""

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
        # Untruncated, otherwise the tests below would silently pass.
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
    # If the row is already there, the existing one is looked up.
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
    assert json.loads(params[10]) == ["x", "y"]          # options


def test_the_set_name_is_written_with_the_exercise(fake_db):
    # A set drawn purely from the pool reads its name from here, not from a model.
    calls = fake_db(rows=[(1,)])
    repo.add_pool_items(9, "quiz", "B1", [{"front": "a", "back": "A"}], ["a"],
                        set_title="Passiv im Labor")
    anweisung, params = next((c[1], c[2]) for c in calls if c[0] == "execute")
    assert "set_title" in anweisung
    assert params[6] == "Passiv im Labor"


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
    """What an earlier draw already took has to be told to the query."""
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
    # Two NULLs do not count as equal in Postgres.
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


# --- schon gesehen, dauerhaft ---------------------------------------------------

def test_the_take_excludes_via_the_permanent_seen_table(fake_db):
    """A deleted set must not free the exercise up again, so the live join is gone."""
    calls = fake_db(rows=[])
    repo.take_from_pool(9, "quiz", None, 3, 5)
    sql, params = next((c[1], c[2]) for c in calls if c[0] == "execute")
    assert "aia_exercise_pool_seen" in sql
    assert "aia_exercise_sets" not in sql
    assert 3 in params, "die Nutzer-Id muss noch in die Abfrage wandern"


def test_ignoring_seen_drops_the_check_entirely(fake_db):
    """The last-resort draw must be able to reach already-seen exercises too."""
    calls = fake_db(rows=[])
    repo.take_from_pool(9, "quiz", None, 3, 5, ignore_seen=True)
    sql, params = next((c[1], c[2]) for c in calls if c[0] == "execute")
    assert "aia_exercise_pool_seen" not in sql
    assert 3 not in params, "ohne den Check braucht die Abfrage die Nutzer-Id nicht mehr"


def test_seen_fingerprints_reads_from_the_permanent_table(fake_db):
    """The fingerprint history must survive a deleted set just like the pool exclusion."""
    calls = fake_db(rows=[("a",)])
    repo.seen_fingerprints(3, "quiz")
    sql = next(c[1] for c in calls if c[0] == "execute")
    assert "aia_exercise_pool_seen" in sql
    assert "aia_exercise_sets" not in sql


# --- aufraeumen ----------------------------------------------------------------

def test_clearing_writes_the_content_back_before_deleting(fake_db):
    """Otherwise a finished set goes empty because someone swapped the source."""
    calls = fake_db()
    repo.clear_pool_for_source(9)
    anweisungen = [c[1] for c in calls if c[0] == "execute"]
    assert anweisungen[0].startswith("UPDATE aia_exercise_items"), \
        "erst zurueckschreiben, dann loeschen"
    assert any("DELETE FROM aia_exercise_pool" in a for a in anweisungen)


# --- the presentation format --------------------------------------------------

def test_the_kind_of_a_grammar_item_is_stored(fake_db):
    """Without the kind the pool cannot serve a format selection."""
    calls = fake_db(rows=[(5,)])
    repo.add_pool_items(
        9, "grammatik", "B1",
        [{"front": "f", "back": "b", "_kind": "cloze"}], ["fp"], 4)

    sql, params = calls[0][1], calls[0][2]
    assert "kind" in sql
    # Checked by position, a shift would write into the neighbouring column.
    assert params[4] == "cloze"


def test_an_item_without_a_kind_stores_null(fake_db):
    """Every other tool has no kinds, the column stays empty there."""
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
    """Mixed takes everything, legacy rows without a kind included."""
    calls = fake_db()
    repo.take_from_pool(9, "quiz", None, 3, 5)

    assert "p.kind" not in calls[0][1]


def test_the_exclusion_and_the_format_choice_keep_their_order(fake_db):
    """If text and values drift apart, the query looks for the wrong thing."""
    calls = fake_db()
    repo.take_from_pool(9, "grammatik", None, 3, 5, 4,
                        exclude_ids=[11], kinds=["cloze"])

    params = calls[0][2]
    assert list(params).index([11]) < list(params).index(["cloze"])


# --- Aufwaermen: Erzeugungen je Vorrat zaehlen -----------------------------------

def test_counting_a_generation_adds_one_and_commits(fake_db):
    calls = fake_db()
    repo.count_pool_run(9, "quiz", "B1")
    sql, params = next((c[1], c[2]) for c in calls if c[0] == "execute")
    assert "INSERT INTO aia_exercise_pool_runs" in sql
    assert "runs = aia_exercise_pool_runs.runs + 1" in sql
    assert params == (9, "quiz", "B1", None)
    assert ("commit", None, None) in calls, "ohne commit oeffnet der Vorrat nie"


def test_the_count_matches_the_pool_key_with_coalesce(fake_db):
    """Two NULLs do not count as equal in Postgres, the level-free pool would never add up."""
    calls = fake_db()
    repo.count_pool_run(9, "quiz", None)
    sql = next(c[1] for c in calls if c[0] == "execute")
    assert "COALESCE(level, '')" in sql
    assert "COALESCE(topic_id, 0)" in sql


def test_a_source_is_warm_from_twenty_generations(fake_db):
    calls = fake_db(rows=[(9,)])
    assert repo.warm_pool_sources([9, 10], "quiz", "B1") == {9}
    sql, params = next((c[1], c[2]) for c in calls if c[0] == "execute")
    assert "runs >= %s" in sql
    assert repo.POOL_WARMUP_RUNS == 20
    assert repo.POOL_WARMUP_RUNS in params


def test_the_warmup_is_read_per_level_and_topic(fake_db):
    calls = fake_db(rows=[])
    repo.warm_pool_sources([9], "grammatik", "B1", 42)
    sql, params = next((c[1], c[2]) for c in calls if c[0] == "execute")
    assert "COALESCE(level, '') = COALESCE(%s, '')" in sql
    assert "COALESCE(topic_id, 0) = COALESCE(%s, 0)" in sql
    assert "B1" in params and 42 in params


def test_asking_for_no_sources_touches_no_connection(monkeypatch):
    def boom():
        raise AssertionError("es wurde keine Quelle genannt")

    monkeypatch.setattr(repo, "get_connection", boom)
    assert repo.warm_pool_sources([], "quiz", None) == set()


def test_clearing_a_source_starts_its_count_over(fake_db):
    """A changed source is new material, the first sets must be fresh again."""
    calls = fake_db()
    repo.clear_pool_for_source(9)
    anweisungen = [(c[1], c[2]) for c in calls if c[0] == "execute"]
    assert any("DELETE FROM aia_exercise_pool_runs" in sql and params == (9,)
               for sql, params in anweisungen)
