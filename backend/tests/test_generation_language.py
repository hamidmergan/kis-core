"""The tools generate in the teaching language, from two separate sources."""

import pytest

from src.features.ai_assistant.tasks._helpers import (
    LEARNING_TOOLS,
    TOOL_OUTPUT_LANGUAGE,
    learning_tools_language,
    tool_output_language,
)


def _setting(monkeypatch, value):
    monkeypatch.setattr("src.features.admin.repository.settings.get_setting",
                        lambda key, default="": value)


def test_german_is_the_default():
    assert TOOL_OUTPUT_LANGUAGE == "German"
    assert tool_output_language(None) == ("de", "German")


def test_the_workspace_decides(monkeypatch):
    monkeypatch.setattr("src.database.get_aia_workspace_by_id",
                        lambda _id: {"id": 7, "diagnosis_language": "fr"})
    assert tool_output_language(7) == ("fr", "French")


@pytest.mark.parametrize("code,name", [
    ("de", "German"), ("en", "English"), ("fr", "French"), ("es", "Spanish"),
    ("it", "Italian"), ("tr", "Turkish"), ("ar", "Arabic"), ("ru", "Russian"),
])
def test_every_offered_language_resolves(monkeypatch, code, name):
    """All eight from the dropdown have to arrive, not just the two common ones."""
    monkeypatch.setattr("src.database.get_aia_workspace_by_id",
                        lambda _id: {"id": 7, "diagnosis_language": code})
    assert tool_output_language(7) == (code, name)


def test_a_workspace_without_a_setting_gets_the_default(monkeypatch):
    monkeypatch.setattr("src.database.get_aia_workspace_by_id", lambda _id: {"id": 7})
    assert tool_output_language(7) == ("de", "German")


def test_an_unknown_code_falls_back_instead_of_crashing(monkeypatch):
    # A value nobody offers any more must not fail a job.
    monkeypatch.setattr("src.database.get_aia_workspace_by_id",
                        lambda _id: {"id": 7, "diagnosis_language": "kli"})
    assert tool_output_language(7) == ("de", "German")


def test_an_unreadable_workspace_falls_back(monkeypatch):
    def boom(_id):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.get_aia_workspace_by_id", boom)
    assert tool_output_language(7) == ("de", "German")


def test_a_missing_workspace_falls_back(monkeypatch):
    monkeypatch.setattr("src.database.get_aia_workspace_by_id", lambda _id: None)
    assert tool_output_language(7) == ("de", "German")


def test_no_tool_derives_its_output_language_from_the_locale():
    """The derivation from the interface language must not reappear anywhere."""
    import pathlib

    wurzel = (pathlib.Path(__file__).resolve().parent.parent
              / "src" / "features" / "ai_assistant" / "tasks")
    treffer = [
        p.relative_to(wurzel).as_posix()
        for p in wurzel.rglob("*.py")
        if '"English" if' in p.read_text(encoding="utf-8")
    ]
    assert treffer == [], f"Ableitung aus dem locale wieder aufgetaucht in: {treffer}"


# The four learning tools follow one setting for the whole installation.


def test_learning_tools_default_to_german(monkeypatch):
    # Nothing configured: get_setting passes its own default through.
    monkeypatch.setattr("src.features.admin.repository.settings.get_setting",
                        lambda key, default="": default)
    assert learning_tools_language() == ("de", "German")


@pytest.mark.parametrize("code,name", [
    ("de", "German"), ("en", "English"), ("fr", "French"), ("es", "Spanish"),
    ("it", "Italian"), ("tr", "Turkish"), ("ar", "Arabic"), ("ru", "Russian"),
])
def test_learning_tools_take_every_offered_language(monkeypatch, code, name):
    _setting(monkeypatch, code)
    assert learning_tools_language() == (code, name)


def test_learning_tools_fall_back_on_an_unknown_code(monkeypatch):
    # Otherwise the code would sit verbatim in the instruction: 'Write it in kli.'
    _setting(monkeypatch, "kli")
    assert learning_tools_language() == ("de", "German")


def test_only_the_four_learning_tools_follow_the_setting():
    """The language trainer must not move along when management switches."""
    assert LEARNING_TOOLS == {"karteikarten", "quiz"}
    for sprachtrainer in ("flashcards", "grammatik", "wortschatz"):
        assert sprachtrainer not in LEARNING_TOOLS


# What reaches the learner has to be in the same language.


@pytest.mark.parametrize("code", ["de", "en", "fr", "es", "it", "tr", "ar", "ru"])
def test_true_false_labels_exist_in_every_language(code):
    """A French question must not be followed by German true/false labels."""
    from src.features.ai_assistant.tasks.language_training._source_mc import _verdict_labels

    wahr, falsch = _verdict_labels(code)
    assert wahr and falsch and wahr != falsch


def test_true_false_labels_fall_back_to_german():
    from src.features.ai_assistant.tasks.language_training._source_mc import _verdict_labels

    assert _verdict_labels("kli") == ("Richtig", "Falsch")
    assert _verdict_labels("") == ("Richtig", "Falsch")


@pytest.mark.parametrize("language", [
    "German", "English", "French", "Spanish", "Italian", "Turkish", "Arabic", "Russian",
])
def test_the_glossary_fallback_question_speaks_every_language(language):
    from src.features.ai_assistant.tasks.language_training._glossary import _fallback_karteikarte

    karte = _fallback_karteikarte(
        {"term_de": "Fluchtweg", "definition": "Weg nach draussen"}, language)
    assert "Fluchtweg" in karte["front"]
    if language != "German":
        assert karte["front"] != _fallback_karteikarte(
            {"term_de": "Fluchtweg", "definition": "x"}, "German")["front"]
