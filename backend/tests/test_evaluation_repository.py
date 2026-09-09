"""The config read: the on/off switch and the seed content are independent."""
from unittest.mock import patch

from src.features.evaluation import repository as repo
from src.features.evaluation.service import default_config


def _settings(store: dict):
    """A get_setting stand-in backed by a plain dict, empty string for anything unset."""
    return lambda key, default="": store.get(key, default)


def test_switching_active_before_ever_saving_the_form_still_activates_it():
    """Regression: toggling the switch used to fall through to the compiled-in seed,
    which hardcodes active=False, silently ignoring what was just saved."""
    store = {"evaluation_active": "true"}
    with patch("src.features.evaluation.repository.get_setting", _settings(store)):
        config = repo.get_config()
    assert config["active"] is True
    assert config["title"] == default_config()["title"]


def test_a_fresh_install_reads_as_inactive_with_the_seed_content():
    with patch("src.features.evaluation.repository.get_setting", _settings({})):
        config = repo.get_config()
    assert config["active"] is False
    # Question ids are random per call, so compare the wording, not identity.
    assert [f["text"] for f in config["questions"]] == [f["text"] for f in default_config()["questions"]]


def test_a_fresh_install_starts_without_an_intro_step():
    """No seed intro text, so the first question opens right away."""
    with patch("src.features.evaluation.repository.get_setting", _settings({})):
        config = repo.get_config()
    assert config["intro_text"] == ""


def test_a_fresh_install_thanks_the_visitor_at_the_end():
    with patch("src.features.evaluation.repository.get_setting", _settings({})):
        config = repo.get_config()
    assert "Dank" in config["outro_text"]


def test_an_emptied_intro_stays_empty():
    """The admin cleared the field on purpose, the seed text must not creep back in."""
    store = {
        "evaluation_title": "Kurze Evaluation",
        "evaluation_intro_text": "",
        "evaluation_outro_text": "",
        "evaluation_questions": '[{"id": "q1", "type": "text", "text": "Wie war es?"}]',
    }
    with patch("src.features.evaluation.repository.get_setting", _settings(store)):
        config = repo.get_config()
    assert config["intro_text"] == ""
    assert config["outro_text"] == ""


def test_saved_content_is_read_back_verbatim():
    store = {
        "evaluation_active": "true",
        "evaluation_title": "Feedback zum Tag der Lehre",
        "evaluation_intro_text": "Willkommen",
        "evaluation_outro_text": "Danke",
        "evaluation_questions": '[{"id": "q1", "type": "text", "text": "Wie war es?"}]',
    }
    with patch("src.features.evaluation.repository.get_setting", _settings(store)):
        config = repo.get_config()
    assert config["title"] == "Feedback zum Tag der Lehre"
    assert config["questions"] == [{"id": "q1", "type": "text", "text": "Wie war es?"}]
