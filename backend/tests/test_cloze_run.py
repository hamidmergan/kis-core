"""Checks the cloze run: pool hit, source mode and card mode."""

import types

import pytest

import src.database as db
import src.features.ai_assistant.tasks.language_training._context as _context
import src.features.ai_assistant.tasks.language_training._pool as _pool
import src.features.ai_assistant.tasks.language_training._source_cloze as _source_cloze
import src.features.ai_assistant.tasks.language_training._variation as _variation
from src.features.ai_assistant.tasks.language_training._source_cloze import run_cloze_set


def _boom(name: str):
    """A call here is a test failure, not behaviour that should be checked."""
    def f(*_a, **_k):
        raise AssertionError(f"{name} haette in diesem Zweig nicht laufen duerfen")
    return f


def _ctx_stub():
    return types.SimpleNamespace(context="[Q.pdf, S. 1] Text", multi_label="Q.pdf",
                                 source_by_name={}, sections={1: "Q.pdf"})


def _run(mod_set: dict, count: int = 5, uuids=("u1",)):
    run_cloze_set(1, mod_set, user_id=7, count=count, client=None, model=None,
                  language="German", adaptive_suffix="", uuids=list(uuids))


@pytest.fixture
def seen():
    return {"finalized": None, "failed": False}


@pytest.fixture(autouse=True)
def _stub_db_and_titles(monkeypatch, seen):
    """What every test needs unchanged."""
    def finalize(set_id, title, items, header=None, user_id=None):
        seen["finalized"] = {"set_id": set_id, "title": title, "items": items,
                             "user_id": user_id}

    def fail(_set_id):
        seen["failed"] = True

    monkeypatch.setattr(db, "finalize_exercise_set", finalize)
    monkeypatch.setattr(db, "fail_exercise_set", fail)
    monkeypatch.setattr(_variation, "build_title_avoidance_block", lambda *a, **k: "")
    return seen


# ─── no set without a source ──────────────────────────────────────────────────

def test_ohne_quellen_scheitert_das_set_sofort(monkeypatch, seen):
    # Without this guard the rest would run on with an empty source list.
    monkeypatch.setattr(_pool, "take", _boom("der Vorrat"))
    monkeypatch.setattr(_context, "build_source_context", _boom("der Kontextbau"))
    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source", _boom("das Modell"))

    _run({"mode": "source"}, uuids=[])

    assert seen["failed"] is True
    assert seen["finalized"] is None


# ─── Vorrats-Treffer ──────────────────────────────────────────────────────────

def test_ein_vorrats_treffer_finalisiert_mit_dem_titel_aus_extras_ohne_modellaufruf(
    monkeypatch, seen,
):
    # The title of a pooled text sits in extras.title, not on the set.
    aus_vorrat = [{"front": "Text {{1}}.", "back": "Text X.",
                  "extras": {"title": "Anlage und Filter", "gaps": [{"base": "a", "solution": "X"}]}}]
    monkeypatch.setattr(_pool, "take", lambda *a, **k: aus_vorrat)
    # A hit ends the run before context building and the model.
    monkeypatch.setattr(_context, "build_source_context", _boom("der Kontextbau"))
    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source", _boom("das Modell"))
    monkeypatch.setattr(_pool, "store", _boom("das Einlagern"))

    _run({"mode": "source"})

    assert seen["finalized"]["title"] == "Anlage und Filter"
    assert seen["finalized"]["items"] == aus_vorrat
    assert seen["failed"] is False


@pytest.mark.parametrize("extras", [{}, None], ids=["leere_extras", "keine_extras"])
def test_ein_vorrats_treffer_von_vor_dem_titel_bekommt_trotzdem_einen(
    monkeypatch, seen, extras,
):
    # Older pool rows carry no title, then the fallback applies.
    monkeypatch.setattr(_pool, "take", lambda *a, **k: [
        {"front": "Text {{1}}.", "back": "Text X.", "extras": extras},
    ])
    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source", _boom("das Modell"))

    _run({"mode": "source"})

    assert seen["finalized"]["title"] == "Lückentext"
    assert seen["finalized"]["title"] != ""


def test_der_vorrat_wird_nach_der_bestellten_luecken_zahl_gefragt(monkeypatch, seen):
    # The ordered gap count has to reach the pool as a filter.
    erhalten = {}

    def fake_take(uuids, tool, level, user_id, limit, topic_id=None, kinds=None):
        erhalten["limit"] = limit
        erhalten["kinds"] = kinds
        return []

    monkeypatch.setattr(_pool, "take", fake_take)
    monkeypatch.setattr(_context, "build_source_context", lambda *a, **k: _ctx_stub())
    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source",
                        lambda *a, **k: ([{"front": "f", "back": "b", "extras": {}}], "T"))
    monkeypatch.setattr(_pool, "store", lambda *a, **k: None)

    _run({"mode": "source"}, count=5)

    assert erhalten["limit"] == 1, "eine Vorratszeile ist ein GANZER Text"
    assert erhalten["kinds"] == ["5"]


# ─── source mode builds context without a section quota (regression) ─────────

def test_quellenmodus_baut_den_kontext_ohne_abschnitts_quote(monkeypatch, seen):
    # With count the section quota broke the continuous text apart.
    monkeypatch.setattr(_pool, "take", lambda *a, **k: [])
    erhalten = {}

    def fake_build(*a, **k):
        erhalten["args"] = a
        erhalten["kwargs"] = k
        return _ctx_stub()

    monkeypatch.setattr(_context, "build_source_context", fake_build)
    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source",
                        lambda *a, **k: ([{"front": "f", "back": "b", "extras": {}}], "T"))
    monkeypatch.setattr(_pool, "store", lambda *a, **k: None)

    _run({"mode": "source"}, count=5)

    assert erhalten["args"] == (["u1"], "wortschatz")
    assert "count" not in erhalten["kwargs"]


def test_die_titel_vermeidung_erreicht_den_erzeuger(monkeypatch, seen):
    # Without passing it through a second set would get the same title.
    monkeypatch.setattr(_pool, "take", lambda *a, **k: [])
    monkeypatch.setattr(_context, "build_source_context", lambda *a, **k: _ctx_stub())
    monkeypatch.setattr(_variation, "build_title_avoidance_block",
                        lambda *a, **k: "\n\nMEIDE: 'Anlage und Filter'")
    erhalten = {}

    def fake_generate(client, model, ctx, count, words=None, **kw):
        erhalten["title_avoidance"] = kw.get("title_avoidance")
        return [{"front": "f", "back": "b", "extras": {}}], "T"

    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source", fake_generate)
    monkeypatch.setattr(_pool, "store", lambda *a, **k: None)

    _run({"mode": "source", "workspace_id": 7}, count=5)

    assert erhalten["title_avoidance"] == "\n\nMEIDE: 'Anlage und Filter'"


def test_kind_verlaesst_die_aufgabe_wieder_bevor_sie_gespeichert_wird(monkeypatch, seen):
    # _kind is a helper field and has no place in the saved set.
    monkeypatch.setattr(_pool, "take", lambda *a, **k: [])
    monkeypatch.setattr(_context, "build_source_context", lambda *a, **k: _ctx_stub())
    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source", lambda *a, **k: (
        [{"front": "f", "back": "b", "extras": {}, "_kind": "5"}], "T"))
    monkeypatch.setattr(_pool, "store", lambda *a, **k: None)

    _run({"mode": "source"}, count=5)

    assert all("_kind" not in i for i in seen["finalized"]["items"])


# ─── Kartenmodus ──────────────────────────────────────────────────────────────

def test_kartenmodus_liest_die_vorderseiten_als_wortliste(monkeypatch, seen):
    # Without passing it through the model would freely choose the words.
    monkeypatch.setattr(db, "get_exercise_set_with_items", lambda _id: {
        "items": [{"front": "arbeiten"}, {"front": "wechseln"}],
    })
    monkeypatch.setattr(_pool, "take", _boom("der Vorrat"))
    monkeypatch.setattr(_context, "build_source_context", lambda *a, **k: _ctx_stub())
    erhalten = {}

    def fake_generate(client, model, ctx, count, words=None, **kw):
        erhalten["words"] = words
        return [{"front": "f", "back": "b", "extras": {}}], "T"

    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source", fake_generate)
    monkeypatch.setattr(_pool, "store", _boom("das Einlagern"))

    _run({"mode": "cards", "flashcard_set_id": 42})

    assert erhalten["words"] == ["arbeiten", "wechseln"]


def test_kartenmodus_mit_mehr_karten_als_bestellt_behaelt_die_bestellte_zahl(
    monkeypatch, seen,
):
    monkeypatch.setattr(db, "get_exercise_set_with_items", lambda _id: {
        "items": [{"front": w} for w in "abcdefgh"],
    })
    monkeypatch.setattr(_context, "build_source_context", lambda *a, **k: _ctx_stub())
    erhalten = {}

    def fake_generate(client, model, ctx, count, words=None, **kw):
        erhalten["count"] = count
        return [{"front": "f", "back": "b", "extras": {}}], "T"

    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source", fake_generate)

    _run({"mode": "cards", "flashcard_set_id": 1}, count=5)

    assert erhalten["count"] == 5, "8 Karten fuer 5 bestellte Luecken: 5 bleibt 5"


def test_kartenmodus_mit_weniger_karten_als_bestellt_kuerzt_die_zahl(monkeypatch, seen):
    monkeypatch.setattr(db, "get_exercise_set_with_items", lambda _id: {
        "items": [{"front": w} for w in "abc"],
    })
    monkeypatch.setattr(_context, "build_source_context", lambda *a, **k: _ctx_stub())
    erhalten = {}

    def fake_generate(client, model, ctx, count, words=None, **kw):
        erhalten["count"] = count
        return [{"front": "f", "back": "b", "extras": {}}], "T"

    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source", fake_generate)

    _run({"mode": "cards", "flashcard_set_id": 1}, count=10)

    assert erhalten["count"] == 3, "nur 3 Karten vorhanden, 10 waeren erlogen"


@pytest.mark.parametrize("karten", [{"items": []}, None], ids=["leeres_set", "kein_set"])
def test_kartenmodus_ohne_karten_scheitert_statt_zu_erzeugen(monkeypatch, seen, karten):
    monkeypatch.setattr(db, "get_exercise_set_with_items", lambda _id: karten)
    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source", _boom("das Modell"))
    monkeypatch.setattr(_context, "build_source_context", _boom("der Kontextbau"))

    _run({"mode": "cards", "flashcard_set_id": 1})

    assert seen["failed"] is True
    assert seen["finalized"] is None


def test_kartenmodus_mit_ausschliesslich_leeren_vorderseiten_scheitert(monkeypatch, seen):
    # A set with nothing but empty fronts is not really a set.
    monkeypatch.setattr(db, "get_exercise_set_with_items", lambda _id: {
        "items": [{"front": "   "}, {"front": ""}],
    })
    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source", _boom("das Modell"))

    _run({"mode": "cards", "flashcard_set_id": 1})

    assert seen["failed"] is True


def test_kartenmodus_fragt_den_vorrat_nie(monkeypatch, seen):
    # In card mode there is no pool, the cards are personal.
    monkeypatch.setattr(db, "get_exercise_set_with_items", lambda _id: {
        "items": [{"front": "arbeiten"}],
    })
    monkeypatch.setattr(_pool, "take", _boom("der Vorrat"))
    monkeypatch.setattr(_pool, "store", _boom("das Einlagern"))
    monkeypatch.setattr(_context, "build_source_context", lambda *a, **k: _ctx_stub())
    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source",
                        lambda *a, **k: ([{"front": "f", "back": "b", "extras": {}}], "T"))

    _run({"mode": "cards", "flashcard_set_id": 1}, count=1)

    assert seen["failed"] is False


def test_quellenmodus_fragt_den_vorrat(monkeypatch, seen):
    # In source mode the pool has to be asked.
    gefragt = []
    monkeypatch.setattr(_pool, "take", lambda *a, **k: gefragt.append(1) or [])
    monkeypatch.setattr(_context, "build_source_context", lambda *a, **k: _ctx_stub())
    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source",
                        lambda *a, **k: ([{"front": "f", "back": "b", "extras": {}}], "T"))
    monkeypatch.setattr(_pool, "store", lambda *a, **k: None)

    _run({"mode": "source"})

    assert len(gefragt) == 1


# ─── schon gesehen, dauerhaft ─────────────────────────────────────────────────

def test_ein_vorrats_treffer_wird_dem_ziehenden_nutzer_zugeschrieben(monkeypatch, seen):
    """Otherwise the pool would keep handing this same text back after a deleted set."""
    aus_vorrat = [{"front": "Text {{1}}.", "back": "Text X.",
                  "extras": {"title": "T", "gaps": [{"base": "a", "solution": "X"}]}}]
    monkeypatch.setattr(_pool, "take", lambda *a, **k: aus_vorrat)

    _run({"mode": "source"})

    assert seen["finalized"]["user_id"] == 7


def test_ein_frisch_erzeugter_text_wird_ebenfalls_zugeschrieben(monkeypatch, seen):
    monkeypatch.setattr(_pool, "take", lambda *a, **k: [])
    monkeypatch.setattr(_context, "build_source_context", lambda *a, **k: _ctx_stub())
    monkeypatch.setattr(_source_cloze, "generate_cloze_from_source",
                        lambda *a, **k: ([{"front": "f", "back": "b", "extras": {}}], "T"))
    monkeypatch.setattr(_pool, "store", lambda *a, **k: None)

    _run({"mode": "source"})

    assert seen["finalized"]["user_id"] == 7
