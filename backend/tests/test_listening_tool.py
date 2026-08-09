"""Hör- und Leseverstehen: Richtig/Falsch-Aussagen über alle gewählten Quellen.

Das Werkzeug läuft mechanisch wie das Quiz, ein rotierendes Fenster über den ganzen
Kontext, eine Aufgabe je Stelle. Unterschieden wird es allein durch die Form: eine
Aussage, zwei Optionen, Richtig oder Falsch. Vier-Optionen-Aufgaben gehören dem Quiz und
dürfen hier nicht entstehen, weder aus dem Prompt noch aus einer Antwort des Modells.

Getestet wird deshalb dreierlei: dass der Prompt nichts anderes bestellt, dass eine
trotzdem gelieferte Vier-Optionen-Aufgabe durchfällt, und die Prüfsteine, die verhindern,
dass aus der Aussage wieder eine Wissensfrage wird.

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


def _true(statement=_STATEMENT, **extra):
    return {"statement": statement, "answer": True, **extra}


def _false(statement=_STATEMENT, **extra):
    return {"statement": statement, "answer": False, **extra}


@pytest.fixture
def gen(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_listening as mod

    monkeypatch.setattr(mod, "title_from_items", lambda *a, **k: "T")
    # Die Attribution fragt pgvector. Hier wird nur festgehalten, WOMIT sie gerufen wird.
    seen = {}
    monkeypatch.setattr(mod, "attach_chips_cited",
                        lambda items, claims, ctx, **kw: seen.update(
                            items=[dict(i) for i in items], claims=claims, ctx=ctx, kw=kw))
    mod._seen = seen
    return mod


# ── Richtig/Falsch ───────────────────────────────────────────────────────────

def test_a_true_statement_becomes_two_options_with_richtig_first(gen):
    client, _calls = _make_client(_payload(_true()))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert len(items) == 1
    assert items[0]["front"] == _STATEMENT
    assert items[0]["options"] == ["Richtig", "Falsch"]
    assert items[0]["correct_idx"] == 0


def test_a_false_statement_points_at_falsch(gen):
    client, _calls = _make_client(_payload(_false()))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert items[0]["correct_idx"] == 1
    assert items[0]["back"] == "Falsch"


def test_the_verdict_labels_follow_the_locale(gen):
    client, _calls = _make_client(_payload(_true("The values are stored.")))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="en")

    assert items[0]["options"] == ["True", "False"]


def test_a_statement_without_a_verdict_is_dropped(gen):
    client, _calls = _make_client(_payload(
        {"statement": _STATEMENT},
        _true("Die Werte liegen ein Jahr lang."),
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert [i["front"] for i in items] == ["Die Werte liegen ein Jahr lang."]


def test_a_verdict_that_is_not_a_boolean_is_dropped(gen):
    """"answer": "true" ist ein String und kein Urteil. Ohne die Prüfung stünde die
    Aufgabe mit einer geratenen Antwort im Satz."""
    client, _calls = _make_client(_payload({"statement": _STATEMENT, "answer": "true"}))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert items == []


# ── Keine Vier-Optionen-Aufgabe, das ist das Quiz ────────────────────────────

def test_a_four_option_item_is_dropped(gen):
    """Der Grund für das ganze Werkzeug: es soll nicht aussehen wie das Quiz. Der Prompt
    bestellt nur Aussagen, das Modell hält sich nicht immer daran, also fällt eine
    Frage mit Optionen im Code durch."""
    client, _calls = _make_client(_payload(
        {"question": "Was heißt das?",
         "options": ["Die Werte gehen an die Auswertung", "B", "C", "D"], "correct_idx": 0},
        _true(),
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert [i["front"] for i in items] == [_STATEMENT]


def test_the_prompt_orders_statements_and_nothing_else(gen):
    client, calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(), 8, locale="de")

    system = calls[0][0]["content"]
    assert "Write exactly 8 statements" in system
    # Weder die alten Fragearten noch überhaupt eine Option dürfen bestellt werden. Die
    # Namen stehen in Anführungszeichen, so wie sie im Prompt standen: "paraphrase" ist
    # als Feldwert verboten, als englisches Wort in einer Regel aber harmlos.
    for wort in ('"kind"', '"paraphrase"', '"reference"', '"inference"',
                 "correct_idx", "options"):
        assert wort not in system


def test_every_item_carries_only_the_two_verdicts(gen):
    """Die Ansicht unterscheidet die Werkzeuge an der Anzahl der Optionen. Zwei heißt
    Richtig/Falsch, vier heißt Quiz."""
    client, _calls = _make_client(_payload(
        _true(), _false("Die Werte liegen zehn Jahre lang."),
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert len(items) == 2
    assert all(len(i["options"]) == 2 for i in items)


def test_the_example_from_the_prompt_is_never_taken_as_an_item(gen):
    """Das Beispiel steht im Prompt, damit das Modell die Form nachahmt. Schreibt es
    das Beispiel selbst ab, ist das keine Aufgabe zur Quelle."""
    client, _calls = _make_client(_payload(
        _true("Bei sinkender Temperatur arbeitet die Anlage weniger wirtschaftlich."),
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert items == []


# ── Das Sprachniveau ─────────────────────────────────────────────────────────

def test_below_b2_the_statement_stays_on_what_the_source_says(gen):
    client, calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(), 5, locale="de", level="A2")

    system = calls[0][0]["content"]
    assert "says directly" in system
    assert "FOLLOWS from the material" not in system


def test_from_b2_the_statement_may_be_a_conclusion(gen):
    """Ohne diese Zeile ist jede Aufgabe Wiedererkennen, und für C1 ist das keine
    Übung mehr. Die Form bleibt trotzdem Richtig/Falsch."""
    client, calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(), 5, locale="de", level="C1")

    assert "FOLLOWS from the material" in calls[0][0]["content"]


def test_without_a_level_the_statement_stays_on_what_the_source_says(gen):
    client, calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(), 5, locale="de")

    assert "says directly" in calls[0][0]["content"]


# ── Aufnahmen brauchen keine Sonderbehandlung mehr ───────────────────────────

def test_a_recording_gets_no_block_of_its_own(gen):
    """Die Aufnahme-Sperre gab es nur, weil zitierende Fragearten keinen gesprochenen
    Wortlaut abdrucken durften. Diese Arten gibt es nicht mehr, und "nie wörtlich
    abschreiben" steht schon in den Regeln für die Aussage."""
    client, calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(both=True), 5, locale="de")

    system = calls[0][0]["content"]
    assert "RECORDINGS" not in system
    assert "Never copy the source verbatim" in system


def test_an_item_on_a_recording_stays(gen):
    """Eine Aussage über eine Aufnahme ist nach dem Hören zu entscheiden. Sie wurde
    früher weggeworfen, wenn sie zitierte, und zitiert wird jetzt nie."""
    client, _calls = _make_client(_payload(_true()))

    def _chips(items, claims, ctx, **kw):
        for item in items:
            item["sources"] = [{"source_label": "VL1.mp4", "page_number": 1,
                                "start_time": 42.0}]
            item["source_label"] = "VL1.mp4"

    gen.attach_chips_cited = _chips

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(media=True), 1,
                                                       locale="de")

    assert len(items) == 1
    # Die Hilfsfelder dürfen nicht in der gespeicherten Zeile landen.
    assert "_claim" not in items[0]


# ── Prompt-Aufbau ────────────────────────────────────────────────────────────

def test_the_material_goes_in_and_the_examples_come_after_it(gen):
    client, calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(), 5, locale="de")

    user = calls[0][1]["content"]
    assert MATERIAL in user
    # Die Beispiele stehen HINTER dem Material. Davor wurden sie als Aufgabe 1
    # abgeschrieben, siehe das Grammatik-Quiz.
    assert user.index(MATERIAL) < user.index("examples of the SHAPE")


def test_it_says_that_this_is_not_a_knowledge_quiz(gen):
    client, calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(), 5, locale="de")

    assert "THIS IS NOT A KNOWLEDGE QUIZ" in calls[0][0]["content"]


def test_the_rules_from_test_construction_are_in_the_prompt(gen):
    """Ohne sie ist die Aussage ohne die Quelle lösbar: Absolutwörter sind fast immer
    falsch, Weichmacher fast immer richtig, und ein Modell ohne Vorgabe schreibt fast
    nur wahre Sätze."""
    client, calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(), 5, locale="de")

    system = calls[0][0]["content"]
    assert "About half of the statements must be false" in system
    assert "Never use absolute words" in system


def test_every_item_comes_from_a_different_place(gen):
    client, calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(), 15, locale="de")

    assert "DIFFERENT place" in calls[0][0]["content"]


def test_the_adaptive_suffix_and_the_coverage_block_are_appended(gen):
    client, calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(both=True), 4, locale="de",
                                       adaptive_suffix="\n\nADAPT", coverage="\n\nCOVER")

    system = calls[0][0]["content"]
    assert system.endswith("\n\nADAPT\n\nCOVER")


# ── Fundstelle ───────────────────────────────────────────────────────────────

def test_items_carry_the_source_and_page_the_model_named(gen):
    """Das Werkzeug fragt im Prompt nach source_label und page_number. Die Angabe ist
    die verlässlichste für eine geschriebene Quelle, weil das Modell im Moment des
    Schreibens weiß, wo es gelesen hat."""
    client, _calls = _make_client(_payload(
        _true(source_label="Skript.pdf", page_number=4)))

    gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    handed = gen._seen["items"][0]
    assert handed["_page"] == 4
    assert handed["_source_label"] == "Skript.pdf"


def test_a_source_the_model_invented_never_becomes_the_chip(gen):
    """Die Angabe des Modells wird benutzt, aber nicht geglaubt. Weder die Datei noch
    die Seite stehen im Kontext, also müssen beide durchfallen und die Attribution
    entscheidet."""
    from src.features.ai_assistant.tasks.language_training import _attribution

    client, _calls = _make_client(_payload(
        _true(source_label="Erfunden.pdf", page_number=99)))

    gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    handed = gen._seen["items"][0]
    ctx = gen._seen["ctx"]
    assert ctx.context == MATERIAL
    assert _attribution._cited_chip(handed, ctx, {1: "Skript.pdf"}) is None
    assert _attribution._named_source_id(handed, ctx) is None


def test_the_claim_leaves_the_verdict_label_out(gen):
    """Gesucht wird die Fundstelle über die Aussage. "Richtig" steht in keiner Quelle
    und würde die Suche verwässern."""
    client, _calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(), 1, locale="de")

    assert gen._seen["claims"] == [_STATEMENT]


def test_the_section_claim_travels_for_the_coverage_check(gen):
    client, _calls = _make_client(_payload(_true(section=2)))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(both=True), 1,
                                                       locale="de")

    assert items[0]["_section"] == 2


# ── Bis zur bestellten Anzahl ────────────────────────────────────────────────

def test_a_mostly_filtered_run_gets_a_second_throw(gen):
    thin = _payload({"question": "Was?", "options": ["A", "B", "C", "D"], "correct_idx": 0})
    good = _payload(_true(), _true("Die Werte liegen ein Jahr lang."))
    client, calls = _make_client(thin, good)

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 4, locale="de")

    assert len(calls) >= 2
    assert len(items) == 2


def test_a_short_draw_is_topped_up_to_the_requested_count(gen):
    """Wer zehn Aufgaben bestellt, will zehn. Die Filter werfen weg, und ohne
    Nachschlag kam ein kurzes Set heraus."""
    erst = _payload(_true())
    dann = _payload(_true("Die Werte liegen ein Jahr lang."))
    client, calls = _make_client(erst, dann)

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert len(items) == 2
    assert len(calls) == 2


def test_the_top_up_asks_only_for_what_is_missing(gen):
    client, calls = _make_client(_payload(_true()), _payload(
        _true("Die Werte liegen ein Jahr lang."),
        _true("Die Auswertung findet im Rechenzentrum statt."),
    ))

    gen.generate_listening_from_source(client, "m", _ctx(), 3, locale="de")

    assert "Write exactly 2 statements" in calls[1][0]["content"]


def test_the_top_up_lets_a_passage_be_used_again_in_other_words(gen):
    """Das Material ist endlich. Steht die Anzahl noch nicht, darf dieselbe Stelle
    ein zweites Mal drankommen, solange die Aussage anders lautet."""
    client, calls = _make_client(_payload(_true()))

    gen.generate_listening_from_source(client, "m", _ctx(), 4, locale="de")

    assert "TOP-UP" not in calls[0][0]["content"]
    assert "TOP-UP" in calls[1][0]["content"]


def test_after_three_throws_it_gives_up(gen):
    """Mehr als drei bringt nichts, und das Anfragen-Kontingent teilt sich die
    ganze Hochschule."""
    client, calls = _make_client(_payload({"statement": _STATEMENT}))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 4, locale="de")

    assert items == []
    assert len(calls) == 3


def test_a_full_run_is_not_thrown_twice(gen):
    """Liefert ein Wurf die bestellte Anzahl, ist Schluss. Ein weiterer Aufruf kostet
    nur vom hochschulweit geteilten Kontingent."""
    client, calls = _make_client(_payload(
        _true(), _false("Die Werte liegen zehn Jahre lang.")))

    gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert len(calls) == 1


# ── Doppler ──────────────────────────────────────────────────────────────────

def test_the_same_claim_in_other_words_is_not_taken_twice(gen):
    """Der Nachschlag darf zu einer Stelle zurückkehren, aber nicht dasselbe zweimal
    behaupten. Am laufenden System gemessen (2026-08-06)."""
    client, _calls = _make_client(_payload(
        _true("Die Messwerte werden alle zehn Sekunden gespeichert."),
        _true("Die Messwerte werden von dem Server alle zehn Sekunden gespeichert."),
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert len(items) == 1


def test_the_same_claim_with_an_extra_clause_is_not_taken_twice(gen):
    """Am laufenden System gemessen (Set 1783): derselbe Satz mit anderem Monat und
    einem Nebensatz stand ein zweites Mal im Set.

    Der Anteil gemeinsamer Wörter reicht dagegen nicht: er teilt durch den LÄNGEREN
    Satz, und ein angehängter Nebensatz verdünnt ihn unter jede Schwelle (hier 0,53).
    Gezählt wird deshalb, wie viel vom kürzeren Satz im längeren steckt (hier 0,89).
    """
    client, _calls = _make_client(_payload(
        _true("Die Literaturrecherche muss bis zum 15. Mai abgeschlossen sein."),
        _false("Die Literaturrecherche muss bis zum 15. April abgeschlossen sein, "
               "damit die Arbeit rechtzeitig fertig wird."),
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert len(items) == 1


def test_two_claims_about_different_things_both_stay(gen):
    """Die Gegenprobe. Der Doppler-Filter darf nicht jede zweite Aufgabe fressen,
    nur weil zwei Sätze aus derselben Quelle dieselben Fachwörter tragen."""
    client, _calls = _make_client(_payload(
        _true("Die Messwerte gehen an die Auswertung."),
        _true("Der Server speichert alle zehn Sekunden."),
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert len(items) == 2


def test_two_claims_about_one_deadline_are_not_the_same_claim(gen):
    """Die enge Gegenprobe, ebenfalls aus Set 1783: wann die Recherche fertig sein
    muss und wann sie beginnt, teilen fast den halben Satz und sind trotzdem zwei
    Aufgaben. Sie liegen bei 0,56 und müssen bleiben."""
    client, _calls = _make_client(_payload(
        _true("Die Literaturrecherche muss bis zum 15. Mai abgeschlossen sein."),
        _true("Die Literaturrecherche soll nach der Konferenz in der nächsten "
              "Woche beginnen und bis zum 15. laufen."),
    ))

    items, _title = gen.generate_listening_from_source(client, "m", _ctx(), 2, locale="de")

    assert len(items) == 2


def test_unusable_json_yields_nothing_rather_than_raising(gen):
    client, _calls = _make_client("kein JSON")

    items, title = gen.generate_listening_from_source(client, "m", _ctx(), 3, locale="de")

    assert items == [] and title == ""
