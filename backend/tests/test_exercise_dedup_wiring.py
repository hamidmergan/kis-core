"""Der Vorrat im fertigen Auftrag.

Zuerst der Vorrat, dann das Modell. Erzeugt wird nur der Fehlbetrag, und was dabei
entsteht, wandert in den Vorrat und steht ab dann allen offen.

Aussortiert wird nach der Erzeugung, nicht im Prompt: alte Aufgaben in den Prompt zu
schreiben wurde schon einmal gebaut und zurueckgenommen, weil das Modell sie abschreibt
(siehe ``_variation``).

Kein DB- und kein Netzzugriff, Datenbank und Generierung sind ausgetauscht.
"""

import pytest

from src.features.ai_assistant.tasks.language_training import run_generate_exercise_set


@pytest.fixture
def stack(monkeypatch):
    """Haengt den Auftrag an Attrappen und haelt fest, was gespeichert wird."""
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

        def finalize_exercise_set(self, set_id, title, items, header=None):
            seen["finalized"] = {"title": title, "items": items, "header": header}

        def fail_exercise_set(self, _id):
            seen["failed"] = True

    monkeypatch.setattr(mod, "db", _DB())
    monkeypatch.setattr(mod, "_get_llm_client", lambda: (object(), "m", "p"))
    monkeypatch.setattr(mod, "build_adaptive_tool_suffix", lambda *a, **k: "")
    monkeypatch.setattr(mod, "build_title_avoidance_block", lambda *a, **k: "")
    monkeypatch.setattr(mod, "resolve_set_title", lambda *a, **k: "Endgueltig")
    monkeypatch.setattr(mod, "coverage_rule", lambda *a, **k: "")
    # Kein Abschnitts-Nachschlag: hier geht es um Vorrat und Doppler.
    monkeypatch.setattr(mod, "missing_section_uuids", lambda *a, **k: [])
    # Vorrat und Historie standardmaessig leer, jeder Test setzt was er braucht.
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: [])
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: [])
    monkeypatch.setattr(
        mod, "store_in_pool",
        lambda items, ctx, tool, level, topic_id=None:
            seen["eingelagert"].append((tool, level, list(items), topic_id)))

    class _Ctx:
        sections = {1: "A.pdf"}
        source_by_name = {"A.pdf": {"id": 1}}

    monkeypatch.setattr(mod, "build_source_context", lambda *a, **k: _Ctx())
    return mod, seen


def _cards(*fronts):
    return [{"front": f, "back": f.upper()} for f in fronts]


def _pool_cards(*fronts):
    """Wie sie aus dem Vorrat kommen: mit Verweis."""
    return [{"front": f, "back": f.upper(), "pool_item_id": 100 + i}
            for i, f in enumerate(fronts)]


def _run(count=3, tool="quiz"):
    run_generate_exercise_set(1, 7, tool, "source", count, source_uuids=["u-1"])


def _generator(mod, monkeypatch, seen, *runden):
    """Setzt die Generierung auf eine Folge von Rueckgaben je Aufruf."""
    lauf = {"n": 0}

    def _gen(*a, **k):
        lauf["n"] += 1
        seen["erzeugt"] = lauf["n"]
        return list(runden[min(lauf["n"], len(runden)) - 1]), "T"

    monkeypatch.setattr(mod, "generate_mc_from_source", _gen)
    return lauf


# --- Vorrat zuerst ------------------------------------------------------------

def test_a_full_pool_costs_no_generation(stack, monkeypatch):
    """Der Kern der Sache: reicht der Vorrat, laeuft kein Modell."""
    mod, seen = stack
    monkeypatch.setattr(mod, "take_from_pool",
                        lambda *a, **k: _pool_cards("a", "b", "c"))
    lauf = _generator(mod, monkeypatch, seen, _cards("x"))

    _run(count=3)

    assert lauf["n"] == 0, "der Vorrat hat gereicht, es darf nichts erzeugt werden"
    assert [i["front"] for i in seen["finalized"]["items"]] == ["a", "b", "c"]


def test_a_full_pool_does_not_even_build_the_context(stack, monkeypatch):
    # Das Fenster zu bauen kostet Datenbankarbeit und rueckt den Lesezeiger weiter.
    # Beides waere umsonst, wenn ohnehin nichts erzeugt wird.
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
    tool, level, eingelagert, thema = seen["eingelagert"][0]
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
    """Ihre Aufgaben haengen zusaetzlich am Thema, also fragt sie mit Thema an.

    Ohne das kaeme eine Passiv-Aufgabe in einer Konjunktiv-Uebung heraus.
    """
    mod, seen = stack
    gefragt = {}

    def _take(uuids, tool, level, user_id, count, topic_id=None):
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

    assert [i["front"] for i in seen["finalized"]["items"]] == ["Peer Review", "Exposé"]


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
    # Gleiche Regel wie beim Abschnitts-Nachschlag: was fertig ist, wird gespeichert.
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
    assert [i["front"] for i in seen["finalized"]["items"]] == ["Peer Review"]


def test_a_set_that_is_nothing_but_repeats_does_not_get_saved(stack, monkeypatch):
    # Das Dokument hat nichts Neues mehr herzugeben. Ein leeres Set als fertig
    # anzubieten waere schlimmer als ein gescheitertes.
    mod, seen = stack
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: ["a", "b"])
    _generator(mod, monkeypatch, seen, _cards("a", "b"), _cards("a", "b"))

    _run(count=2)

    assert seen["failed"] is True
    assert seen["finalized"] is None


def test_a_pool_item_is_not_dropped_as_a_repeat(stack, monkeypatch):
    """Was der Vorrat liefert, hat diese Person nachweislich noch nicht gehabt.

    Der Filter darf es also nicht nachtraeglich wieder wegwerfen, auch wenn die
    Historie zufaellig eine aehnliche Vorderseite enthaelt.
    """
    mod, seen = stack
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: _pool_cards("a", "b"))
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: ["a", "b"])
    _generator(mod, monkeypatch, seen, _cards("c"))

    _run(count=2)

    assert [i["front"] for i in seen["finalized"]["items"]] == ["a", "b"]
