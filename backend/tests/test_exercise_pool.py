"""Checks taking and storing, the database side needs a real Postgres."""

import types

import pytest

from src.features.ai_assistant.tasks.language_training import _pool


# --- who takes part at all ----------------------------------------------------

@pytest.mark.parametrize("tool", ["flashcards", "karteikarten", "quiz"])
def test_the_three_source_tools_use_the_pool(tool):
    assert _pool.uses_pool(tool, "source") is True


def test_the_grammar_tool_is_in_too():
    # Grammar splits its pool by topic as well.
    assert _pool.uses_pool("grammatik", "source") is True


def test_the_glossary_mode_stays_out():
    # Draws from a finished term list and does not have the problem at all.
    assert _pool.uses_pool("quiz", "glossary") is False


# --- welches Niveau ------------------------------------------------------------

def test_without_an_adaptive_suffix_the_level_is_none(monkeypatch):
    """The suffix is empty as soon as one of the three gates is closed."""
    monkeypatch.setattr("src.database.get_user_language_level",
                        lambda _u: {"language_level": "B1"})
    assert _pool.pool_level("", 7) is None


def test_with_a_suffix_the_stored_level_decides(monkeypatch):
    monkeypatch.setattr("src.database.get_user_language_level",
                        lambda _u: {"language_level": "B1"})
    assert _pool.pool_level("... auf B1 ...", 7) == "B1"


def test_an_unreadable_level_falls_back_to_the_level_free_pool(monkeypatch):
    def boom(_u):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.get_user_language_level", boom)
    assert _pool.pool_level("...", 7) is None


# --- ziehen --------------------------------------------------------------------

def _stub_pool(monkeypatch, bestand: dict):
    """The stub stays stateless, like the real query."""
    gefragt = []

    def take(source_id, tool, level, user_id, limit, topic_id=None, exclude_ids=None,
             kinds=None, ignore_seen=False):
        gefragt.append((source_id, limit, topic_id, ignore_seen))
        raus = set(exclude_ids or ())
        vorrat = [f for f in bestand.get(source_id, []) if f"{source_id}-{f}" not in raus]
        return [{"id": f"{source_id}-{f}", "front": f, "back": ""} for f in vorrat[:limit]]

    monkeypatch.setattr("src.database.take_from_pool", take)
    monkeypatch.setattr("src.database.get_aia_source",
                        lambda u: {"id": int(u.removeprefix("u"))})
    return gefragt


def test_nothing_to_take_without_sources_or_count(monkeypatch):
    _stub_pool(monkeypatch, {})
    assert _pool.take([], "quiz", None, 1, 5) == []
    assert _pool.take(["u1"], "quiz", None, 1, 0) == []
    assert _pool.take(["u1"], "quiz", None, None, 5) == []


def test_the_take_is_spread_evenly_over_the_sources(monkeypatch):
    _stub_pool(monkeypatch, {1: list("abcdef"), 2: list("ghijkl"), 3: list("mnopqr")})
    out = _pool.take(["u1", "u2", "u3"], "quiz", None, 1, 6)
    fronts = [i["front"] for i in out]
    assert len(fronts) == 6
    # two from each source, not six from the first
    assert len([f for f in fronts if f in "abcdef"]) == 2
    assert len([f for f in fronts if f in "ghijkl"]) == 2
    assert len([f for f in fronts if f in "mnopqr"]) == 2


def test_a_thin_source_lets_the_others_make_up_for_it(monkeypatch):
    """This replaces the old balancing that squeezed the context together."""
    _stub_pool(monkeypatch, {1: ["a"], 2: list("bcdefgh")})
    out = _pool.take(["u1", "u2"], "quiz", None, 1, 6)
    assert len(out) == 6, "die volle Bestellung, obwohl Quelle 1 nur eine Aufgabe hat"


def test_an_empty_pool_yields_nothing_rather_than_failing(monkeypatch):
    _stub_pool(monkeypatch, {1: [], 2: []})
    assert _pool.take(["u1", "u2"], "quiz", None, 1, 5) == []


def test_never_more_than_ordered(monkeypatch):
    _stub_pool(monkeypatch, {1: list("abcdefghij")})
    assert len(_pool.take(["u1"], "quiz", None, 1, 3)) == 3


def test_a_failing_pool_read_means_everything_gets_generated(monkeypatch):
    # The pool is a shortcut, not a requirement.
    def boom(*_a, **_k):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.get_aia_source", boom)
    assert _pool.take(["u1"], "quiz", None, 1, 5) == []


def test_a_pool_smaller_than_the_order_does_not_repeat_itself(monkeypatch):
    """Without exclusion the second round returns the same exercises."""
    _stub_pool(monkeypatch, {1: list("abcd")})
    fronts = [i["front"] for i in _pool.take(["u1"], "quiz", None, 1, 10)]
    assert fronts == list("abcd"), f"jede Aufgabe genau einmal, nicht {fronts}"


def test_the_second_round_brings_new_tasks_and_not_the_first_ones_again(monkeypatch):
    _stub_pool(monkeypatch, {1: list("abcdefgh"), 2: []})
    fronts = [i["front"] for i in _pool.take(["u1", "u2"], "quiz", None, 1, 6)]
    assert len(fronts) == len(set(fronts)), f"Doppler im selben Satz: {fronts}"
    assert len(fronts) == 6, "Quelle 1 hat genug, die leere Quelle darf das nicht kosten"


def test_the_same_task_from_two_sources_counts_once(monkeypatch):
    """Two sources can hold the same exercise, the index sits per source."""
    _stub_pool(monkeypatch, {1: ["a"], 2: ["a"]})
    fronts = [i["front"] for i in _pool.take(["u1", "u2"], "quiz", None, 1, 2)]
    assert fronts == ["a"], f"derselbe Satz zweimal in einer Uebung: {fronts}"


def test_an_exhausted_source_is_not_asked_again(monkeypatch):
    """Whoever delivers less than ordered is empty, a second query only costs."""
    gefragt = _stub_pool(monkeypatch, {1: ["a"], 2: ["b"]})
    _pool.take(["u1", "u2"], "quiz", None, 1, 6)
    assert [q[0] for q in gefragt] == [1, 2], "keine zweite Runde auf leere Vorraete"


def test_pool_rows_carry_their_reference(monkeypatch):
    _stub_pool(monkeypatch, {1: ["a"]})
    out = _pool.take(["u1"], "quiz", None, 1, 1)
    assert out[0]["pool_item_id"] == "1-a"


# --- der Notfall-Nachschlag, wenn wirklich nichts Neues mehr da ist ------------

def test_ignore_seen_reaches_the_query(monkeypatch):
    """The last-resort draw must ask the pool to include already-seen exercises."""
    gefragt = _stub_pool(monkeypatch, {1: list("abc")})
    _pool.take(["u1"], "quiz", None, 1, 2, ignore_seen=True)
    assert all(eintrag[3] is True for eintrag in gefragt)


def test_without_the_flag_the_query_stays_as_it_was(monkeypatch):
    gefragt = _stub_pool(monkeypatch, {1: list("abc")})
    _pool.take(["u1"], "quiz", None, 1, 2)
    assert all(eintrag[3] is False for eintrag in gefragt)


def test_an_earlier_draws_ids_are_excluded_from_the_start(monkeypatch):
    """A repeat-fallback must not hand back what this order already holds."""
    _stub_pool(monkeypatch, {1: list("abc")})
    out = _pool.take(["u1"], "quiz", None, 1, 3, exclude_ids=["1-a"])
    fronts = [i["front"] for i in out]
    assert "a" not in fronts
    assert set(fronts) == {"b", "c"}


# --- einlagern -----------------------------------------------------------------

def _ctx(**quellen):
    return types.SimpleNamespace(source_by_name=quellen)


def _stub_store(monkeypatch, platz=100):
    gespeichert = []

    def add(source_id, tool, level, items, fingerprints, topic_id=None, set_title=None):
        gespeichert.append((source_id, tool, level, [i["front"] for i in items], topic_id,
                            set_title))
        return [f"neu-{f}" for f in fingerprints]

    monkeypatch.setattr("src.database.add_pool_items", add)
    monkeypatch.setattr("src.database.pool_size", lambda *a: 0)
    monkeypatch.setattr("src.database.POOL_MAX_ITEMS", platz, raising=False)
    return gespeichert


def test_generated_items_go_into_the_pool_of_their_source(monkeypatch):
    gespeichert = _stub_store(monkeypatch)
    items = [{"front": "a", "source_label": "A.pdf"},
             {"front": "b", "source_label": "B.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}, "B.pdf": {"id": 2}}), "quiz", "B1")

    assert sorted(gespeichert) == [(1, "quiz", "B1", ["a"], None, None),
                                  (2, "quiz", "B1", ["b"], None, None)]
    assert items[0]["pool_item_id"] == "neu-a"


def test_an_item_without_a_source_stays_out_of_the_pool(monkeypatch):
    # Without an assignable source the exercise stays in the set and carries its own content.
    gespeichert = _stub_store(monkeypatch)
    items = [{"front": "a", "source_label": "Unbekannt.pdf"}, {"front": "b"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "quiz", None)

    assert gespeichert == []
    assert "pool_item_id" not in items[0]


def test_what_came_from_the_pool_is_not_stored_again(monkeypatch):
    gespeichert = _stub_store(monkeypatch)
    items = [{"front": "a", "source_label": "A.pdf", "pool_item_id": 5}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "quiz", None)
    assert gespeichert == []


def test_a_full_pool_stops_taking_more(monkeypatch):
    gespeichert = []
    monkeypatch.setattr(
        "src.database.add_pool_items",
        lambda s, t, l, items, f, tid=None, set_title=None:
            gespeichert.append(len(items)) or [1] * len(items))
    monkeypatch.setattr("src.database.pool_size", lambda *a: 1000)
    items = [{"front": "a", "source_label": "A.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "quiz", None)
    assert gespeichert == []


def test_a_failing_store_does_not_reach_the_caller(monkeypatch):
    # Storing is an improvement, the set is saved either way.
    def boom(*_a, **_k):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.pool_size", boom)
    items = [{"front": "a", "source_label": "A.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "quiz", None)  # darf nicht werfen
    assert "pool_item_id" not in items[0]


def test_storing_nothing_is_harmless(monkeypatch):
    gespeichert = _stub_store(monkeypatch)
    _pool.store([], _ctx(), "quiz", None)
    assert gespeichert == []


# --- grammar splits by topic as well ------------------------------------------

def test_the_grammar_pool_is_asked_per_topic(monkeypatch):
    gefragt = _stub_pool(monkeypatch, {1: list("abc")})
    _pool.take(["u1"], "grammatik", None, 1, 2, topic_id=42)
    assert all(eintrag[2] == 42 for eintrag in gefragt), \
        "ohne Thema kaeme eine Passiv-Aufgabe in einer Konjunktiv-Uebung heraus"


def test_grammar_items_are_stored_under_their_topic(monkeypatch):
    gespeichert = _stub_store(monkeypatch)
    items = [{"front": "Der Satz wird gebildet.", "source_label": "A.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "grammatik", "B1", topic_id=42)
    assert gespeichert == [(1, "grammatik", "B1", ["Der Satz wird gebildet."], 42, None)]


def test_a_tool_without_a_topic_stores_none(monkeypatch):
    gespeichert = _stub_store(monkeypatch)
    items = [{"front": "a", "source_label": "A.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "quiz", None)
    assert gespeichert[0][4] is None


# --- fingerprint: length safe for the btree index -----------------------------

def test_a_very_long_front_still_gets_a_storable_fingerprint(monkeypatch):
    # Without truncation a long text blows the index limit and the pool stays empty.
    fingerprints_gesehen = []

    def add(source_id, tool, level, items, fingerprints, topic_id=None, set_title=None):
        fingerprints_gesehen.extend(fingerprints)
        return [f"neu-{f}" for f in fingerprints]

    monkeypatch.setattr("src.database.add_pool_items", add)
    monkeypatch.setattr("src.database.pool_size", lambda *a: 0)
    langer_text = "Die Anlage arbeitet seit gestern wieder ohne Stoerung. " * 100
    items = [{"front": langer_text, "source_label": "A.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "wortschatz", None)

    assert len(fingerprints_gesehen) == 1
    # A fixed value instead of the constant, otherwise the test checks itself.
    assert len(fingerprints_gesehen[0].encode("utf-8")) <= 2700
    # The returned id still arrives, as with every tool.
    assert items[0]["pool_item_id"] == f"neu-{fingerprints_gesehen[0]}"


def test_a_short_front_keeps_its_established_fingerprint():
    # Short fronts have to keep the same fingerprint as before.
    kurz = "Der Satz wird gebildet."
    assert _pool._fingerprint(kurz) == _pool.item_key(kurz)


# --- the set name travels with the exercises ----------------------------------

def test_the_set_name_is_stored_next_to_the_exercises(monkeypatch):
    gespeichert = _stub_store(monkeypatch)
    items = [{"front": "a", "source_label": "A.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "quiz", None,
                set_title="Passiv im Labor")
    assert gespeichert[0][5] == "Passiv im Labor"


def test_a_pooled_set_inherits_the_most_common_name():
    items = [{"set_title": "Passiv im Labor"}, {"set_title": "Passiv im Labor"},
             {"set_title": "Anderes Thema"}]
    assert _pool.title_from_items(items) == "Passiv im Labor"


def test_exercises_without_a_stored_name_yield_nothing():
    # Everything generated before the column existed, the caller keeps its placeholder.
    assert _pool.title_from_items([{"front": "a"}, {"set_title": "   "}]) == ""
    assert _pool.title_from_items([]) == ""
