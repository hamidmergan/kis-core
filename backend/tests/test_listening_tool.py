"""Hör- und Leseverstehen: Verstehensfragen über alle gewählten Quellen.

Das Werkzeug läuft mechanisch wie das Quiz, ein rotierendes Fenster über den ganzen
Kontext, eine Frage je Stelle. Unterschieden wird es allein durch die Frageart. Getestet
wird deshalb zweierlei: dass die Arten so bestellt werden, wie sie bestellt sein sollen,
und die Prüfsteine, die verhindern, dass daraus wieder eine Wissensfrage wird.

Kein DB- und kein Netzzugriff: der Generator bekommt einen Fake-Client, die Attribution
wird abgefangen.
"""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training._context import QuelleContext


def _make_client(*contents):
    """Minimal OpenAI-client stand-in: records every call, antwortet der Reihe nach."""
    calls = []
    queue = list(contents)

    def create(model, messages, **kwargs):
        calls.append(messages)
        content = queue.pop(0) if len(queue) > 1 else queue[0]
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


MATERIAL = (
    "[Skript.pdf, S. 4] Der Server speichert die Messwerte alle zehn Sekunden. Die Werte "
    "gehen danach an die Auswertung im Rechenzentrum. Sie liegen dort ein Jahr lang, "
    "bevor sie gelöscht werden."
)


def _ctx(media=False, both=False):
    """Kontext mit einer PDF, einer Aufnahme oder beidem."""
    pdf = {"id": 1, "uuid": "u-pdf", "filename": "Skript.pdf", "file_type": "pdf"}
    vid = {"id": 2, "uuid": "u-mp4", "filename": "VL1.mp4", "file_type": "mp4"}
    if both:
        by_name = {"Skript.pdf": pdf, "VL1.mp4": vid}
        sections = {1: "Skript.pdf", 2: "VL1.mp4"}
    elif media:
        by_name = {"VL1.mp4": vid}
        sections = {1: "VL1.mp4"}
    else:
        by_name = {"Skript.pdf": pdf}
        sections = {1: "Skript.pdf"}
    return QuelleContext(
        context=MATERIAL, first_label=next(iter(by_name)), multi_label=next(iter(by_name)),
        source_hint="folgender Source", source_by_name=by_name, sections=sections,
        seen_pages_by_source={s["id"]: {4} for s in by_name.values()},
    )


def _payload(*exercises, title="Messwerte"):
    return json.dumps({"title": title, "exercises": list(exercises)})


_STATEMENT = "Die Messwerte werden alle zehn Sekunden gespeichert."


@pytest.fixture
def gen(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_listening as mod

    monkeypatch.setattr(mod, "title_from_items", lambda *a, **k: "T")
    # Die Attribution fragt pgvector. Hier wird nur festgehalten, WOMIT sie gerufen wird.
    seen = {}
    monkeypatch.setattr(mod, "attach_chips",
                        lambda items, claims, ctx, **kw: seen.update(
                            items=items, claims=claims, ctx=ctx, kw=kw))
    mod._seen = seen
    return mod


# ── Richtig/Falsch ───────────────────────────────────────────────────────────

def test_a_true_statement_becomes_two_options_with_richtig_first(gen):
    client, _calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True}))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert len(items) == 1
    assert items[0]["front"] == _STATEMENT
    assert items[0]["options"] == ["Richtig", "Falsch"]
    assert items[0]["correct_idx"] == 0


def test_a_false_statement_points_at_falsch(gen):
    client, _calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": False}))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert items[0]["correct_idx"] == 1
    assert items[0]["back"] == "Falsch"


def test_the_verdict_labels_follow_the_locale(gen):
    client, _calls = _make_client(_payload(
        {"kind": "statement", "statement": "The values are stored.", "answer": True}))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="en")

    assert items[0]["options"] == ["True", "False"]


def test_a_statement_without_a_verdict_is_dropped(gen):
    client, _calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT},
        {"kind": "statement", "statement": _STATEMENT, "answer": True},
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert len(items) == 1


# ── Weltwissen-Sperre ────────────────────────────────────────────────────────

def test_an_answer_that_is_not_in_the_material_is_dropped(gen):
    client, _calls = _make_client(_payload(
        {"kind": "paraphrase", "question": "Was heißt das?",
         "options": ["Der Vertrag läuft im Juli aus", "B", "C", "D"], "correct_idx": 0},
        {"kind": "statement", "statement": _STATEMENT, "answer": True},
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert [i["front"] for i in items] == [_STATEMENT]


def test_an_answer_taken_from_the_material_survives(gen):
    client, _calls = _make_client(_payload(
        {"kind": "paraphrase", "question": "Was heißt das?",
         "options": ["Die Werte gehen an die Auswertung", "B", "C", "D"], "correct_idx": 0},
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert len(items) == 1


def test_an_inference_may_stand_outside_the_material(gen):
    client, _calls = _make_client(_payload(
        {"kind": "inference", "question": "Was folgt daraus?",
         "options": ["Nach einem Jahr sind alte Vorgänge nicht mehr nachvollziehbar",
                     "B", "C", "D"], "correct_idx": 0},
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert len(items) == 1


# ── Formfehler ───────────────────────────────────────────────────────────────

def test_two_identical_options_drop_the_item(gen):
    client, _calls = _make_client(_payload(
        {"kind": "paraphrase", "question": "Was heißt das?",
         "options": ["Die Werte", "die werte", "C", "D"], "correct_idx": 0},
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert items == []


def test_an_option_that_repeats_the_question_drops_the_item(gen):
    client, _calls = _make_client(_payload(
        {"kind": "paraphrase", "question": "Die Werte gehen an die Auswertung",
         "options": ["Die Werte gehen an die Auswertung", "B", "C", "D"], "correct_idx": 0},
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert items == []


def test_the_example_from_the_prompt_is_never_taken_as_an_item(gen):
    client, _calls = _make_client(_payload(
        {"kind": "statement",
         "statement": "Bei sinkender Temperatur arbeitet der Verdichter weniger.",
         "answer": False},
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert items == []


# ── Die Mischung der Fragearten ──────────────────────────────────────────────

def test_the_plan_fills_exactly_the_requested_count(gen):
    assert len(gen.item_plan(15, advanced=False, text_ok=True)) == 15
    assert len(gen.item_plan(5, advanced=True, text_ok=True)) == 5


def test_a_written_source_gets_the_quoting_kinds(gen):
    plan = gen.item_plan(8, advanced=False, text_ok=True)

    assert "paraphrase" in plan and "reference" in plan


def test_recordings_alone_never_get_a_quoting_kind(gen):
    plan = gen.item_plan(8, advanced=True, text_ok=False)

    assert set(plan) <= {"statement", "inference"}


def test_the_inference_arrives_at_b2(gen):
    assert "inference" not in gen.item_plan(8, advanced=False, text_ok=True)
    assert "inference" in gen.item_plan(8, advanced=True, text_ok=True)


def test_the_mix_is_a_number_in_the_prompt(gen):
    client, calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True}))

    gen.generate_listening_from_source(client, "m", _ctx(), 8, locale="de")

    system = calls[0][0]["content"]
    assert "Write exactly 8 items" in system
    assert 'of kind "statement"' in system


def test_the_level_reaches_the_prompt(gen):
    client, calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True}))

    gen.generate_listening_from_source(client, "m", _ctx(), 8, locale="de", level="C1")

    assert 'of kind "inference"' in calls[0][0]["content"]


# ── Aufnahmen: nie Wortlaut ──────────────────────────────────────────────────

def test_a_recording_is_named_in_the_prompt_with_its_section_number(gen):
    client, calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True}))

    gen.generate_listening_from_source(client, "m", _ctx(both=True), 5, locale="de")

    system = calls[0][0]["content"]
    # Der Dateiname allein reicht nicht, das Material trägt die Abschnittsnummer im Kopf.
    assert "SECTION 2 (VL1.mp4)" in system
    assert "NEVER put a sentence from a recording in quotation marks" in system


def test_without_a_recording_the_rule_stays_out(gen):
    client, calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True}))

    gen.generate_listening_from_source(client, "m", _ctx(), 5, locale="de")

    assert "RECORDINGS" not in calls[0][0]["content"]


def test_a_quoting_item_on_a_recording_is_thrown_out(gen):
    """Am echten Lauf gemessen: das Modell hält sich nicht an die Prompt-Regel.

    Von 15 Aufgaben lagen 4 als "Die Quelle sagt: ..." auf einem Video. Die Sperre muss
    deshalb im Code stehen, nach der Attribution, weil vorher die Quelle nicht feststeht.
    """
    client, _calls = _make_client(_payload(
        {"kind": "paraphrase", "question": "Die Quelle sagt: \"Die Werte gehen weg.\"",
         "options": ["Die Werte gehen an die Auswertung", "B", "C", "D"], "correct_idx": 0},
        {"kind": "statement", "statement": _STATEMENT, "answer": True},
    ))

    def _chips(items, claims, ctx, **kw):
        for item in items:
            item["sources"] = [{"source_label": "VL1.mp4", "page_number": 1,
                                "start_time": 42.0}]
            item["source_label"] = "VL1.mp4"

    gen.attach_chips = _chips

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(both=True), 2,
                                                       locale="de")

    assert [i["front"] for i in items] == [_STATEMENT]


def test_a_quoting_item_on_a_written_source_stays(gen):
    client, _calls = _make_client(_payload(
        {"kind": "paraphrase", "question": "Was heißt das?",
         "options": ["Die Werte gehen an die Auswertung", "B", "C", "D"], "correct_idx": 0},
    ))

    def _chips(items, claims, ctx, **kw):
        for item in items:
            item["sources"] = [{"source_label": "Skript.pdf", "page_number": 4,
                                "start_time": None}]
            item["source_label"] = "Skript.pdf"

    gen.attach_chips = _chips

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(both=True), 1,
                                                       locale="de")

    assert len(items) == 1
    # Die Hilfsfelder dürfen nicht in der gespeicherten Zeile landen.
    assert "_kind" not in items[0] and "_claim" not in items[0]


def test_a_set_from_recordings_only_asks_for_no_quoting_kind(gen):
    client, calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True}))

    gen.generate_listening_from_source(client, "m", _ctx(media=True), 8, locale="de",
                                       level="C1")

    system = calls[0][0]["content"]
    assert 'of kind "paraphrase"' not in system
    assert 'of kind "reference"' not in system


# ── Prompt-Aufbau ────────────────────────────────────────────────────────────

def test_the_material_goes_in_and_the_examples_come_after_it(gen):
    client, calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True}))

    gen.generate_listening_from_source(client, "m", _ctx(), 5, locale="de")

    user = calls[0][1]["content"]
    assert MATERIAL in user
    # Die Beispiele stehen HINTER dem Material. Davor wurden sie als Aufgabe 1
    # abgeschrieben, siehe das Grammatik-Quiz.
    assert user.index(MATERIAL) < user.index("Three examples of the SHAPE")


def test_it_says_that_this_is_not_a_knowledge_quiz(gen):
    client, calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True}))

    gen.generate_listening_from_source(client, "m", _ctx(), 5, locale="de")

    assert "THIS IS NOT A KNOWLEDGE QUIZ" in calls[0][0]["content"]


def test_every_item_comes_from_a_different_place(gen):
    client, calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True}))

    gen.generate_listening_from_source(client, "m", _ctx(), 15, locale="de")

    assert "DIFFERENT place" in calls[0][0]["content"]


def test_the_adaptive_suffix_and_the_coverage_block_are_appended(gen):
    client, calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True}))

    gen.generate_listening_from_source(client, "m", _ctx(both=True), 4, locale="de",
                                       adaptive_suffix="\n\nADAPT", coverage="\n\nCOVER")

    system = calls[0][0]["content"]
    assert system.endswith("\n\nADAPT\n\nCOVER")


# ── Fundstelle ───────────────────────────────────────────────────────────────

def test_the_source_is_decided_by_attribution_not_by_the_model(gen):
    client, _calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True,
         "source_label": "Erfunden.pdf", "page_number": 99},
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    # Das Modell darf die Seite nennen, gespeichert wird sie nicht: die Attribution
    # entscheidet. Also darf hier nichts vom Modell in der Zeile stehen.
    assert "source_label" not in items[0]
    assert gen._seen["kw"] == {"multi": False}
    assert gen._seen["ctx"].context == MATERIAL


def test_the_claim_for_a_statement_leaves_the_verdict_label_out(gen):
    client, _calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True},
    ))

    gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert gen._seen["claims"] == [_STATEMENT]


def test_the_claim_for_a_question_carries_the_answer(gen):
    client, _calls = _make_client(_payload(
        {"kind": "paraphrase", "question": "Was heißt das?",
         "options": ["Die Werte gehen an die Auswertung", "B", "C", "D"], "correct_idx": 0},
    ))

    gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert gen._seen["claims"] == ["Was heißt das? Die Werte gehen an die Auswertung"]


def test_the_section_claim_travels_for_the_coverage_check(gen):
    client, _calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True, "section": 2},
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(both=True), 1,
                                                       locale="de")

    assert items[0]["_section"] == 2


# ── Zweiter Wurf ─────────────────────────────────────────────────────────────

def test_a_mostly_filtered_run_gets_a_second_throw(gen):
    thin = _payload({"kind": "paraphrase", "question": "Was?",
                     "options": ["Der Vertrag läuft aus", "B", "C", "D"], "correct_idx": 0})
    good = _payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True},
        {"kind": "statement", "statement": "Die Werte liegen ein Jahr lang.", "answer": True},
    )
    client, calls = _make_client(thin, good)

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 4, locale="de")

    assert len(calls) == 2
    assert len(items) == 2


def test_a_full_run_is_not_thrown_twice(gen):
    client, calls = _make_client(_payload(
        {"kind": "statement", "statement": _STATEMENT, "answer": True},
        {"kind": "statement", "statement": "Die Werte liegen ein Jahr lang.", "answer": True},
    ))

    gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert len(calls) == 1


def test_unusable_json_yields_nothing_rather_than_raising(gen):
    client, _calls = _make_client("kein JSON")

    items, title = gen.generate_listening_from_source(client, "m", _ctx(), 3, locale="de")

    assert items == [] and title == ""
