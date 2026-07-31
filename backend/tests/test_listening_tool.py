"""Hörverstehen: eigenes Werkzeug im Fachsprachentrainer.

Es arbeitet wie das Quiz, hat aber eine dritte Frageart (Richtig/Falsch) und
nimmt ausschliesslich Audio- und Video-Quellen, auch wenn der Lernende zusätzlich
ein PDF angeklickt hat.

Kein DB- und kein Netzzugriff: der Generator bekommt einen Fake-Client, die
Attribution wird ausgehängt (sie hat eigene Tests in test_aia_tool_attribution).
"""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training._context import QuelleContext


def _make_client(content):
    """Minimal OpenAI-client stand-in: records every call, antwortet immer gleich."""
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _ctx():
    return QuelleContext(
        context="[VL1.mp4, 03:20] Der Server speichert die Messwerte alle zehn Sekunden.",
        first_label="VL1.mp4",
        multi_label="VL1.mp4",
        source_hint="folgender Source",
        source_by_name={"VL1.mp4": {"id": 1, "workspace_id": 7}},
        seen_pages_by_source={1: {1}},
    )


def _payload(*exercises):
    return json.dumps({"title": "Messwerte", "exercises": list(exercises)})


_STATEMENT = "Die Messwerte werden alle zehn Sekunden gespeichert."


@pytest.fixture
def gen(monkeypatch):
    """Der Generator mit ausgehängter Attribution, plus die gesammelten Claims."""
    from src.features.ai_assistant.tasks.language_training import _source_listening as mod

    seen = {}

    def fake_attach(items, claims, ctx, multi=False):
        seen["claims"] = list(claims)

    monkeypatch.setattr(mod, "attach_chips", fake_attach)
    monkeypatch.setattr(mod, "title_from_items", lambda *a, **k: "T")
    return mod, seen


# ── Richtig/Falsch ───────────────────────────────────────────────────────────

def test_a_true_statement_becomes_two_options_with_richtig_first(gen):
    mod, _ = gen
    client, _calls = _make_client(_payload({"statement": _STATEMENT, "answer": True}))

    items, _title = mod.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert items[0]["front"] == _STATEMENT
    assert items[0]["options"] == ["Richtig", "Falsch"]
    assert items[0]["correct_idx"] == 0
    assert items[0]["back"] == "Richtig"


def test_a_false_statement_marks_the_second_option(gen):
    mod, _ = gen
    client, _calls = _make_client(_payload({"statement": _STATEMENT, "answer": False}))

    items, _title = mod.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert items[0]["options"] == ["Richtig", "Falsch"]
    assert items[0]["correct_idx"] == 1
    assert items[0]["back"] == "Falsch"


def test_english_sets_get_english_labels(gen):
    mod, _ = gen
    client, _calls = _make_client(_payload({"statement": _STATEMENT, "answer": True}))

    items, _title = mod.generate_listening_from_source(client, "m", _ctx(), 1, locale="en")

    assert items[0]["options"] == ["True", "False"]


def test_a_statement_without_a_verdict_is_dropped(gen):
    """Ohne answer ist nicht entscheidbar, was angekreuzt werden soll."""
    mod, _ = gen
    client, _calls = _make_client(_payload(
        {"statement": _STATEMENT},
        {"statement": "Der Server läuft im Keller.", "answer": False},
    ))

    items, _title = mod.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert len(items) == 1
    assert items[0]["front"] == "Der Server läuft im Keller."


def test_the_source_claim_is_the_statement_alone(gen):
    """Die Antwort ist hier nur das Wort Richtig und taugt nicht zum Suchen der Stelle."""
    mod, seen = gen
    client, _calls = _make_client(_payload({"statement": _STATEMENT, "answer": True}))

    mod.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert seen["claims"] == [_STATEMENT]


# ── Die beiden geerbten Fragearten ───────────────────────────────────────────

def test_the_quiz_kinds_still_work(gen):
    mod, _ = gen
    client, _calls = _make_client(_payload(
        {"question": "Wie oft wird gespeichert?", "options": ["a", "b", "c", "d"], "correct_idx": 2},
        {"sentence": "Gespeichert wird alle ___ Sekunden.", "options": ["fünf", "zehn"],
         "correct_idx": 1},
    ))

    items, _title = mod.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert [i["front"] for i in items] == [
        "Wie oft wird gespeichert?", "Gespeichert wird alle ___ Sekunden."]
    assert [i["back"] for i in items] == ["c", "zehn"]


def test_the_models_section_claim_survives(gen):
    mod, _ = gen
    client, _calls = _make_client(_payload(
        {"statement": _STATEMENT, "answer": True, "section": 2}))

    items, _title = mod.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert items[0]["_section"] == 2


# ── Prompt ───────────────────────────────────────────────────────────────────

def _system_of(calls):
    return calls[0][0]["content"]


def test_the_prompt_asks_for_three_kinds_in_equal_shares(gen):
    mod, _ = gen
    client, calls = _make_client(_payload({"statement": _STATEMENT, "answer": True}))

    mod.generate_listening_from_source(client, "m", _ctx(), 9, locale="de")

    prompt = _system_of(calls)
    assert "statement" in prompt
    assert "one third" in prompt.lower()


def test_the_prompt_carries_the_item_writing_rules(gen):
    """Ohne diese Regeln sind Richtig/Falsch-Aussagen ohne Zuhören lösbar."""
    mod, _ = gen
    client, calls = _make_client(_payload({"statement": _STATEMENT, "answer": True}))

    mod.generate_listening_from_source(client, "m", _ctx(), 6, locale="de")

    prompt = _system_of(calls).lower()
    assert "half" in prompt                 # etwa gleich viele wahre und falsche
    assert "always" in prompt               # keine Absolutwoerter
    assert "verbatim" in prompt             # nicht woertlich abschreiben
    assert "one detail" in prompt           # falsch durch genau eine geaenderte Angabe


def test_the_prompt_is_carried_by_the_shared_blocks(gen):
    """Coverage und Niveau-Anpassung muessen wie beim Quiz ankommen."""
    mod, _ = gen
    client, calls = _make_client(_payload({"statement": _STATEMENT, "answer": True}))

    mod.generate_listening_from_source(
        client, "m", _ctx(), 3, locale="de",
        adaptive_suffix="\n\nADAPT-MARKER", coverage="\n\nCOVERAGE-MARKER")

    prompt = _system_of(calls)
    assert "ADAPT-MARKER" in prompt
    assert "COVERAGE-MARKER" in prompt


# ── Dispatch ─────────────────────────────────────────────────────────────────

@pytest.fixture
def dispatch(monkeypatch):
    """Der Celery-Task ohne DB, ohne Netz. Liefert das benutzte Werkzeug zurück."""
    from src.features.ai_assistant.tasks import language_training as task_mod

    used = {}
    monkeypatch.setattr(task_mod.db, "get_aia_workspace_by_id", lambda wid: {"id": wid})
    monkeypatch.setattr(task_mod.db, "get_exercise_set_with_items",
                        lambda sid: {"user_id": 3, "grammar_type": None})
    monkeypatch.setattr(task_mod.db, "finalize_exercise_set",
                        lambda *a, **k: used.setdefault("finalized", True))
    monkeypatch.setattr(task_mod.db, "fail_exercise_set",
                        lambda *a, **k: used.setdefault("failed", True))
    monkeypatch.setattr(task_mod, "_get_llm_client", lambda: (None, "m", "p"))
    monkeypatch.setattr(task_mod, "build_adaptive_tool_suffix", lambda *a, **k: "")
    monkeypatch.setattr(task_mod, "build_title_avoidance_block", lambda *a, **k: "")
    monkeypatch.setattr(task_mod, "build_source_context", lambda *a, **k: _ctx())
    monkeypatch.setattr(task_mod, "resolve_set_title", lambda *a, **k: "T")

    def recorder(name):
        def gen(*a, **k):
            used["generator"] = name
            return [{"front": "F", "back": "B"}], "T"
        return gen

    monkeypatch.setattr(task_mod, "generate_listening_from_source", recorder("listening"))
    monkeypatch.setattr(task_mod, "generate_mc_from_source", recorder("quiz"))
    return task_mod, used


def test_a_listening_set_is_built_by_the_listening_generator(dispatch):
    task_mod, used = dispatch
    task_mod.run_generate_exercise_set.run(
        1, 7, "hoerverstehen", "source", 6, source_uuids=["uuid-mp4"], locale="de")
    assert used["generator"] == "listening"


def test_the_quiz_keeps_its_own_generator(dispatch):
    task_mod, used = dispatch
    task_mod.run_generate_exercise_set.run(
        1, 7, "quiz", "source", 6, source_uuids=["uuid-a"], locale="de")
    assert used["generator"] == "quiz"


# ── Quellenauswahl: nur Ton und Bild ─────────────────────────────────────────

FILES = {
    "uuid-pdf": {"filename": "Skript.pdf", "file_type": "pdf"},
    "uuid-mp4": {"filename": "VL1.mp4", "file_type": "mp4"},
    "uuid-mp3": {"filename": "Podcast.mp3", "file_type": "mp3"},
}


@pytest.fixture
def _sources(monkeypatch):
    monkeypatch.setattr(
        "src.database.get_aia_source", lambda uuid: FILES.get(uuid))


def test_pdfs_drop_out_of_a_listening_set(_sources):
    from src.features.ai_assistant.routes.language_training.exercises import (
        _media_source_uuids,
    )
    picked = ["uuid-pdf", "uuid-mp4", "uuid-mp3"]
    assert _media_source_uuids(picked) == ["uuid-mp4", "uuid-mp3"]


def test_the_learner_order_is_kept(_sources):
    from src.features.ai_assistant.routes.language_training.exercises import (
        _media_source_uuids,
    )
    assert _media_source_uuids(["uuid-mp3", "uuid-mp4"]) == ["uuid-mp3", "uuid-mp4"]


def test_only_pdfs_means_nothing_to_listen_to(_sources):
    from src.features.ai_assistant.routes.language_training.exercises import (
        _media_source_uuids,
    )
    assert _media_source_uuids(["uuid-pdf"]) == []


def test_an_unknown_source_is_no_media_source(_sources):
    from src.features.ai_assistant.routes.language_training.exercises import (
        _media_source_uuids,
    )
    assert _media_source_uuids(["uuid-weg"]) == []


# ── Statistik ────────────────────────────────────────────────────────────────

def test_listening_counts_as_language_training():
    """Sonst taucht die geübte Zeit in keiner der beiden Auswertungen auf."""
    from src.features.ai_assistant.repository.stats import (
        LANGUAGE_TRAINING_TOOLS, LERNTOOLS_TOOLS, sql_tool_list,
    )
    assert "hoerverstehen" in LANGUAGE_TRAINING_TOOLS
    assert "hoerverstehen" not in LERNTOOLS_TOOLS
    assert "'hoerverstehen'" in sql_tool_list(LANGUAGE_TRAINING_TOOLS)


# ── Route: was aus der Auswahl im Satz landet ────────────────────────────────

@pytest.fixture
def create_set(monkeypatch, _sources):
    """Die Erzeugungs-Route ohne DB, Kontingent und Celery.

    Liefert (call, queued): ``call`` startet einen Satz, ``queued`` sammelt, womit
    der Hintergrundauftrag losgeschickt wurde.
    """
    import asyncio

    from src.features.ai_assistant import schemas
    from src.features.ai_assistant.routes.language_training import exercises as route_mod
    from src.tasks import aia_tasks

    queued = {}
    monkeypatch.setattr(route_mod.db, "get_aia_workspace", lambda uuid: {"id": 1, "user_id": 5})
    monkeypatch.setattr(route_mod.db, "is_student_enrolled", lambda *a: True)
    monkeypatch.setattr(route_mod.db, "create_exercise_set_placeholder",
                        lambda **k: {"id": 42, **k})
    monkeypatch.setattr(route_mod, "enforce_aia_burst", lambda *a, **k: None)
    monkeypatch.setattr(route_mod, "enforce_quota", lambda *a, **k: None)
    monkeypatch.setattr(route_mod, "_resolve_source_ids", lambda *a, **k: [1])
    monkeypatch.setattr(aia_tasks.run_generate_exercise_set, "delay",
                        lambda *a, **k: queued.update(args=a, kwargs=k))

    def call(tool, source_uuids):
        body = schemas.CreateSetBody(tool=tool, mode="source", count=6,
                                     source_uuids=source_uuids)
        return asyncio.run(route_mod.create_exercise_set(
            "ws-uuid", body, current_user={"user_id": 5}, locale="de"))

    return call, queued


def test_a_listening_set_is_built_from_the_media_sources_only(create_set):
    call, queued = create_set
    call("hoerverstehen", ["uuid-pdf", "uuid-mp4", "uuid-mp3"])
    assert queued["kwargs"]["source_uuids"] == ["uuid-mp4", "uuid-mp3"]


def test_a_listening_set_without_any_recording_is_refused(create_set):
    from fastapi import HTTPException

    call, _queued = create_set
    with pytest.raises(HTTPException) as err:
        call("hoerverstehen", ["uuid-pdf"])
    assert err.value.status_code == 400


def test_the_quiz_keeps_every_picked_source(create_set):
    call, queued = create_set
    call("quiz", ["uuid-pdf", "uuid-mp4"])
    assert queued["kwargs"]["source_uuids"] == ["uuid-pdf", "uuid-mp4"]
