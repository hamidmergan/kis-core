"""Pool, duplicates and the ordered count in the finished job."""

import pytest

from src.features.ai_assistant.tasks.language_training import run_generate_exercise_set


@pytest.fixture
def stack(monkeypatch):
    """Hooks the job up to stubs and records what gets saved."""
    import src.features.ai_assistant.tasks.language_training as mod

    seen = {"finalized": None, "failed": False, "eingelagert": [], "erzeugt": 0}

    class _DB:
        def get_aia_workspace_by_id(self, _id):
            return {"id": 7}

        def get_exercise_set_with_items(self, _id):
            return {"user_id": 1, "grammar_type": None, "grammar_topic_id": 99}

        def get_grammar_topic(self, _id):
            return {"id": 99, "name": "Passiv"}

        def get_topic_spec(self, _tid, _locale):
            return {"rule": "Regel", "examples": []}

        def finalize_exercise_set(self, set_id, title, items, header=None, user_id=None):
            seen["finalized"] = {"title": title, "items": items, "header": header,
                                 "user_id": user_id}

        def fail_exercise_set(self, _id):
            seen["failed"] = True

    monkeypatch.setattr(mod, "db", _DB())
    monkeypatch.setattr(mod, "_get_llm_client", lambda: (object(), "m", "p"))
    monkeypatch.setattr(mod, "build_adaptive_tool_suffix", lambda *a, **k: "")
    monkeypatch.setattr(mod, "build_title_avoidance_block", lambda *a, **k: "")
    monkeypatch.setattr(mod, "resolve_set_title", lambda *a, **k: "Endgueltig")
    monkeypatch.setattr(mod, "coverage_rule", lambda *a, **k: "")
    # No section top-up, this is about pool and duplicates.
    monkeypatch.setattr(mod, "missing_section_uuids", lambda *a, **k: [])
    # Pool and history empty by default, every test sets what it needs.
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: [])
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: [])
    monkeypatch.setattr(
        mod, "store_in_pool",
        lambda items, ctx, tool, level, topic_id=None, set_title=None:
            seen["eingelagert"].append(
                (tool, level, [dict(i) for i in items], topic_id, set_title)))

    class _Ctx:
        sections = {1: "A.pdf"}
        source_by_name = {"A.pdf": {"id": 1}}

    monkeypatch.setattr(mod, "build_source_context", lambda *a, **k: _Ctx())
    return mod, seen


def _cards(*fronts):
    return [{"front": f, "back": f.upper()} for f in fronts]


def _pool_cards(*fronts):
    """The way they come out of the pool: with a reference."""
    return [{"front": f, "back": f.upper(), "pool_item_id": 100 + i}
            for i, f in enumerate(fronts)]


def _run(count=3, tool="quiz"):
    run_generate_exercise_set(1, 7, tool, "source", count, source_uuids=["u-1"])


def _generator(mod, monkeypatch, seen, *runden):
    """Sets generation to a sequence of return values per call."""
    lauf = {"n": 0}

    def _gen(*a, **k):
        lauf["n"] += 1
        seen["erzeugt"] = lauf["n"]
        return list(runden[min(lauf["n"], len(runden)) - 1]), "T"

    monkeypatch.setattr(mod, "generate_mc_from_source", _gen)
    return lauf


# --- Vorrat zuerst ------------------------------------------------------------

def test_a_full_pool_costs_no_generation(stack, monkeypatch):
    """The heart of it: if the pool suffices, no model runs."""
    mod, seen = stack
    monkeypatch.setattr(mod, "take_from_pool",
                        lambda *a, **k: _pool_cards("a", "b", "c"))
    lauf = _generator(mod, monkeypatch, seen, _cards("x"))

    _run(count=3)

    assert lauf["n"] == 0, "der Vorrat hat gereicht, es darf nichts erzeugt werden"
    assert [i["front"] for i in seen["finalized"]["items"]] == ["a", "b", "c"]


def test_a_full_pool_does_not_even_build_the_context(stack, monkeypatch):
    # Building the window would be wasted when nothing is generated.
    mod, seen = stack
    gebaut = {"n": 0}

    def _ctx(*a, **k):
        gebaut["n"] += 1
        raise AssertionError("Kontext darf hier nicht gebaut werden")

    monkeypatch.setattr(mod, "build_source_context", _ctx)
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: _pool_cards("a", "b"))
    _generator(mod, monkeypatch, seen, _cards("x"))

    _run(count=2)

    assert gebaut["n"] == 0
    assert seen["failed"] is False


def test_only_the_shortfall_is_generated(stack, monkeypatch):
    mod, seen = stack
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: _pool_cards("a", "b"))
    bestellt = {}

    def _gen(client, model, ctx, how_many, **k):
        bestellt["how_many"] = how_many
        return _cards("c", "d", "e")[:how_many], "T"

    monkeypatch.setattr(mod, "generate_mc_from_source", _gen)

    _run(count=5)

    assert bestellt["how_many"] == 3, "zwei kamen aus dem Vorrat, drei fehlen"
    assert [i["front"] for i in seen["finalized"]["items"]] == ["a", "b", "c", "d", "e"]


def test_the_pool_comes_first_in_the_finished_set(stack, monkeypatch):
    mod, seen = stack
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: _pool_cards("alt"))
    _generator(mod, monkeypatch, seen, _cards("neu"))

    _run(count=2)

    fronts = [i["front"] for i in seen["finalized"]["items"]]
    assert fronts == ["alt", "neu"]


# --- Einlagern ----------------------------------------------------------------

def test_what_was_generated_goes_into_the_pool(stack, monkeypatch):
    mod, seen = stack
    _generator(mod, monkeypatch, seen, _cards("a", "b"))

    _run(count=2)

    assert len(seen["eingelagert"]) == 1
    tool, level, eingelagert, thema, _name = seen["eingelagert"][0]
    assert tool == "quiz"
    assert level is None, "ohne Sprachniveau gehoert es in den niveaulosen Vorrat"
    assert [i["front"] for i in eingelagert] == ["a", "b"]
    assert thema is None, "nur die Grammatik traegt ein Thema"


def test_nothing_is_stored_when_the_pool_covered_it(stack, monkeypatch):
    mod, seen = stack
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: _pool_cards("a", "b"))
    _generator(mod, monkeypatch, seen, _cards("x"))

    _run(count=2)

    assert seen["eingelagert"] == []


def test_the_grammar_pool_is_asked_with_its_topic(stack, monkeypatch):
    """Grammar asks with a topic, otherwise the wrong thing comes out."""
    mod, seen = stack
    gefragt = {}

    def _take(uuids, tool, level, user_id, count, topic_id=None, kinds=None):
        gefragt.update(tool=tool, topic_id=topic_id)
        return []

    monkeypatch.setattr(mod, "take_from_pool", _take)
    monkeypatch.setattr(mod, "generate_grammar_from_source",
                        lambda *a, **k: (_cards("g"), "T", None))

    run_generate_exercise_set(1, 7, "grammatik", "source", 1, source_uuids=["u-1"])

    assert gefragt["tool"] == "grammatik"
    assert gefragt["topic_id"] == 99


# --- Doppler ------------------------------------------------------------------

def test_what_this_person_already_had_does_not_come_back(stack, monkeypatch):
    mod, seen = stack
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: ["Abstract"])
    _generator(mod, monkeypatch, seen,
               _cards("Abstract", "Peer Review", "Exposé"))

    _run(count=3)

    # New cards first, the known one only fills the place nothing new was found for.
    assert [i["front"] for i in seen["finalized"]["items"]] == ["Abstract", "Peer Review", "Exposé"]


def test_the_filter_orders_one_refill_and_filters_that_too(stack, monkeypatch):
    mod, seen = stack
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: ["Abstract"])
    lauf = _generator(
        mod, monkeypatch, seen,
        _cards("Abstract", "Peer Review", "Exposé"),   # Lauf 1
        _cards("Abstract", "Gliederung"),              # Nachschlag, ein alter Doppler
    )

    _run(count=3)

    assert lauf["n"] == 2, "genau ein Nachschlag"
    assert [i["front"] for i in seen["finalized"]["items"]] == [
        "Peer Review", "Exposé", "Gliederung"]


def test_no_refill_when_nothing_was_dropped(stack, monkeypatch):
    mod, seen = stack
    lauf = _generator(mod, monkeypatch, seen, _cards("a", "b", "c"))

    _run(count=3)

    assert lauf["n"] == 1
    assert len(seen["finalized"]["items"]) == 3


def test_a_failing_refill_keeps_the_unique_items(stack, monkeypatch):
    # Same rule as for the section top-up: whatever is finished gets saved.
    mod, seen = stack
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: ["Abstract"])
    lauf = {"n": 0}

    def _gen(*a, **k):
        lauf["n"] += 1
        if lauf["n"] == 1:
            return _cards("Abstract", "Peer Review"), "T"
        raise RuntimeError("Connection error.")

    monkeypatch.setattr(mod, "generate_mc_from_source", _gen)

    _run(count=2)

    assert seen["failed"] is False
    assert [i["front"] for i in seen["finalized"]["items"]] == ["Abstract", "Peer Review"]


def test_a_set_of_nothing_but_repeats_is_saved_once_the_material_is_used_up(stack, monkeypatch):
    # Decided 26.09.2026: a used-up source gives known cards again instead of a failed set.
    mod, seen = stack
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: ["a", "b"])
    _generator(mod, monkeypatch, seen, _cards("a", "b"), _cards("a", "b"))

    _run(count=2)

    assert seen["failed"] is False
    assert [i["front"] for i in seen["finalized"]["items"]] == ["a", "b"]


# --- The ordered count --------------------------------------------------------

def test_a_short_run_is_topped_up_to_the_ordered_count(stack, monkeypatch):
    """Even without duplicates a top-up is needed, otherwise the set stays too short."""
    mod, seen = stack
    lauf = _generator(mod, monkeypatch, seen, _cards("a", "b"), _cards("c"))

    _run(count=3)

    assert lauf["n"] == 2, "zwei von drei ist zu wenig, das muss nachbestellt werden"
    assert [i["front"] for i in seen["finalized"]["items"]] == ["a", "b", "c"]


def test_the_top_up_keeps_going_until_the_count_stands(stack, monkeypatch):
    """More than one top-up when the second attempt also delivers too little."""
    mod, seen = stack
    lauf = _generator(mod, monkeypatch, seen,
                      _cards("a"), _cards("b"), _cards("c"))

    _run(count=3)

    assert lauf["n"] == 3
    assert [i["front"] for i in seen["finalized"]["items"]] == ["a", "b", "c"]


def test_the_top_up_stops_when_a_round_brings_nothing_new(stack, monkeypatch):
    """A round without a new exercise ends the top-up right away."""
    mod, seen = stack
    lauf = _generator(mod, monkeypatch, seen, _cards("a"), _cards("a"), _cards("b"))

    _run(count=3)

    assert lauf["n"] == 2
    assert [i["front"] for i in seen["finalized"]["items"]] == ["a"]


def test_the_top_up_has_an_upper_bound(stack, monkeypatch):
    """If every attempt returns only one exercise, the top-up is not endless."""
    mod, seen = stack
    lauf = _generator(mod, monkeypatch, seen,
                      _cards("a"), _cards("b"), _cards("c"), _cards("d"))

    _run(count=10)

    assert lauf["n"] == 3, "ein Wurf und hoechstens zwei Nachschlaege"
    assert len(seen["finalized"]["items"]) == 3


def test_the_pool_counts_towards_the_ordered_number(stack, monkeypatch):
    """The top-up aims at the ordered count, not at the model's share."""
    mod, seen = stack
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: _pool_cards("a", "b"))
    lauf = _generator(mod, monkeypatch, seen, _cards("c"), _cards("d"))

    _run(count=4)

    assert lauf["n"] == 2
    assert [i["front"] for i in seen["finalized"]["items"]] == ["a", "b", "c", "d"]


def test_a_pool_item_is_not_dropped_as_a_repeat(stack, monkeypatch):
    """What the pool delivers the filter must not throw away again."""
    mod, seen = stack
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: _pool_cards("a", "b"))
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: ["a", "b"])
    _generator(mod, monkeypatch, seen, _cards("c"))

    _run(count=2)

    assert [i["front"] for i in seen["finalized"]["items"]] == ["a", "b"]


# --- The format selection -----------------------------------------------------

def _grammar_generator(mod, monkeypatch, *runden):
    """Like the other helper, but for the grammar exercise."""
    lauf = {"n": 0, "kinds": "nie gerufen"}

    def _gen(client, model, ctx, gtype, how_many, **k):
        lauf["n"] += 1
        lauf["kinds"] = k.get("kinds")
        return list(runden[min(lauf["n"], len(runden)) - 1]), "T", {}

    monkeypatch.setattr(mod, "generate_grammar_from_source", _gen)
    return lauf


def _pool_spy(monkeypatch, mod):
    """Captures which format selection the pool was asked with."""
    gefragt = {"kinds": "nie gerufen"}

    def _take(uuids, tool, level, user_id, count, topic_id=None, kinds=None):
        gefragt["kinds"] = kinds
        return []

    monkeypatch.setattr(mod, "take_from_pool", _take)
    return gefragt


def test_the_format_choice_reaches_the_pool(stack, monkeypatch):
    """Without the selection the pool hands out deselected formats."""
    mod, seen = stack
    monkeypatch.setattr(mod.db, "get_exercise_set_with_items", lambda _id: {
        "user_id": 1, "grammar_type": None, "grammar_topic_id": 99,
        "grammar_kinds": ["transform", "cloze"],
    })
    gefragt = _pool_spy(monkeypatch, mod)
    _grammar_generator(mod, monkeypatch, _cards("a", "b", "c"))

    _run(count=3, tool="grammatik")

    assert gefragt["kinds"] == ["transform", "cloze"]


def test_the_format_choice_reaches_the_generator(stack, monkeypatch):
    mod, seen = stack
    monkeypatch.setattr(mod.db, "get_exercise_set_with_items", lambda _id: {
        "user_id": 1, "grammar_type": None, "grammar_topic_id": 99,
        "grammar_kinds": ["choice"],
    })
    lauf = _grammar_generator(mod, monkeypatch, _cards("a", "b", "c"))

    _run(count=3, tool="grammatik")

    assert lauf["kinds"] == ["choice"]


def test_a_mixed_set_asks_for_everything(stack, monkeypatch):
    """A set without a selection is the normal case, then no restriction applies."""
    mod, seen = stack
    gefragt = _pool_spy(monkeypatch, mod)
    lauf = _grammar_generator(mod, monkeypatch, _cards("a", "b", "c"))

    _run(count=3, tool="grammatik")

    assert gefragt["kinds"] is None
    assert lauf["kinds"] is None


def test_a_stale_kind_in_the_column_does_not_break_the_run(stack, monkeypatch):
    """A dead code makes a mixed exercise, not a failure."""
    mod, seen = stack
    monkeypatch.setattr(mod.db, "get_exercise_set_with_items", lambda _id: {
        "user_id": 1, "grammar_type": None, "grammar_topic_id": 99,
        "grammar_kinds": ["malen"],
    })
    lauf = _grammar_generator(mod, monkeypatch, _cards("a", "b", "c"))

    _run(count=3, tool="grammatik")

    assert lauf["kinds"] is None
    assert seen["failed"] is False


# --- Notfall: schon gesehen kommt zurueck --------------------------------------

def test_when_nothing_new_is_left_seen_exercises_fill_the_gap(stack, monkeypatch):
    """The last resort: repeats beat a set that stays too short."""
    mod, seen = stack

    def _take(uuids, tool, level, user_id, count, topic_id=None, kinds=None,
              exclude_ids=None, ignore_seen=False):
        if ignore_seen:
            return [{"front": "Abstract", "back": "ABSTRACT", "pool_item_id": 900}][:count]
        return []

    monkeypatch.setattr(mod, "take_from_pool", _take)
    _generator(mod, monkeypatch, seen, _cards("a"), _cards("a"))  # top-up brings nothing new

    _run(count=3)

    assert {i["front"] for i in seen["finalized"]["items"]} == {"a", "Abstract"}


def test_a_fully_satisfied_top_up_never_asks_for_repeats(stack, monkeypatch):
    mod, seen = stack
    gefragt = {"ignore_seen": "nie gerufen"}

    def _take(uuids, tool, level, user_id, count, topic_id=None, kinds=None,
              exclude_ids=None, ignore_seen=False):
        gefragt["ignore_seen"] = ignore_seen
        return []

    monkeypatch.setattr(mod, "take_from_pool", _take)
    _generator(mod, monkeypatch, seen, _cards("a", "b", "c"))

    _run(count=3)

    assert gefragt["ignore_seen"] is False, "voll bestueckt, der Notfall darf nicht laufen"


def test_the_repeat_fallback_excludes_what_this_order_already_took(stack, monkeypatch):
    mod, seen = stack

    def _take(uuids, tool, level, user_id, count, topic_id=None, kinds=None,
              exclude_ids=None, ignore_seen=False):
        if ignore_seen:
            assert exclude_ids == [500], "der frueh gezogene Vorratseintrag muss ausgeschlossen sein"
            return []
        return [{"front": "alt", "back": "ALT", "pool_item_id": 500}]

    monkeypatch.setattr(mod, "take_from_pool", _take)
    _generator(mod, monkeypatch, seen, _cards("neu"))

    _run(count=3)


def test_the_repeat_fallback_does_not_duplicate_what_the_model_just_generated(
    stack, monkeypatch,
):
    """The fallback draw and the model's own output must not collide either."""
    mod, seen = stack

    def _take(uuids, tool, level, user_id, count, topic_id=None, kinds=None,
              exclude_ids=None, ignore_seen=False):
        if ignore_seen:
            return [{"front": "a", "back": "A", "pool_item_id": 900}][:count]
        return []

    monkeypatch.setattr(mod, "take_from_pool", _take)
    _generator(mod, monkeypatch, seen, _cards("a"), _cards("a"))  # top-up brings nothing new

    _run(count=2)

    fronts = [i["front"] for i in seen["finalized"]["items"]]
    assert fronts == ["a"], f"das Modell hat 'a' schon geliefert, der Notfall darf nicht verdoppeln: {fronts}"


def test_finalize_is_called_with_the_owning_user(stack, monkeypatch):
    mod, seen = stack
    _generator(mod, monkeypatch, seen, _cards("a"))

    _run(count=1)

    assert seen["finalized"]["user_id"] == 1


def test_the_pool_gets_the_kind_the_finished_set_does_not(stack, monkeypatch):
    """_kind travels into the pool and has no place in the saved set."""
    mod, seen = stack
    _grammar_generator(mod, monkeypatch,
                       [{"front": "a", "back": "A", "_kind": "transform"}])

    _run(count=1, tool="grammatik")

    eingelagert = seen["eingelagert"][0][2]
    assert eingelagert[0]["_kind"] == "transform", "der Vorrat braucht die Art"
    assert all("_kind" not in i for i in seen["finalized"]["items"])


# --- the set name: one call delivers exercises and title together --------------

def _named_generator(mod, monkeypatch, fronts, title):
    monkeypatch.setattr(mod, "generate_mc_from_source",
                        lambda *a, **k: (_cards(*fronts), title))


def test_the_name_of_the_generation_call_is_the_name_of_the_set(stack, monkeypatch):
    """No title call of its own, the generation answer already carries the name."""
    mod, seen = stack
    monkeypatch.setattr(mod, "resolve_set_title", lambda w, t, title: title)
    _named_generator(mod, monkeypatch, ("a", "b", "c"), "Passiv im Labor")

    _run(count=3)

    assert seen["finalized"]["title"] == "Passiv im Labor"


def test_the_name_travels_into_the_pool_with_the_exercises(stack, monkeypatch):
    mod, seen = stack
    monkeypatch.setattr(mod, "resolve_set_title", lambda w, t, title: title)
    _named_generator(mod, monkeypatch, ("a",), "Passiv im Labor")

    _run(count=1)

    assert seen["eingelagert"][0][4] == "Passiv im Labor"


def test_a_set_made_purely_from_the_pool_inherits_its_name(stack, monkeypatch):
    """Nothing is generated here, so the name has to come out of the pool."""
    mod, seen = stack
    monkeypatch.setattr(mod, "resolve_set_title", lambda w, t, title: title)
    aus_vorrat = _pool_cards("a", "b")
    for karte in aus_vorrat:
        karte["set_title"] = "Passiv im Labor"
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: aus_vorrat)
    lauf = _generator(mod, monkeypatch, seen, _cards("x"))

    _run(count=2)

    assert lauf["n"] == 0, "der Vorrat hat gereicht, es darf nichts erzeugt werden"
    assert seen["finalized"]["title"] == "Passiv im Labor"


def test_a_pooled_set_without_a_stored_name_falls_back_to_the_source(stack, monkeypatch):
    """Everything pooled before the name was stored, the placeholder must not survive."""
    mod, seen = stack
    monkeypatch.setattr(mod, "resolve_set_title", lambda w, t, title: title)
    monkeypatch.setattr(mod, "label_for_sources", lambda _u: "Skript.pdf")
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: _pool_cards("a", "b"))
    _generator(mod, monkeypatch, seen, _cards("x"))

    _run(count=2)

    assert seen["finalized"]["title"] == "Skript.pdf"
