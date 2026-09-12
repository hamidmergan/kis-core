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


def _writer(store: dict):
    """A set_setting stand-in that writes into the same dict the reader sees."""
    def schreiben(key: str, value: str) -> None:
        store[key] = value
    return schreiben


def test_a_fresh_install_is_not_open_to_everyone():
    with patch("src.features.evaluation.repository.get_setting", _settings({})):
        config = repo.get_config()
    assert config["for_all"] is False
    assert config["reveal_round"] == 0


def test_the_switch_for_everyone_is_read_back():
    store = {"evaluation_for_all": "true", "evaluation_reveal_round": "4"}
    with patch("src.features.evaluation.repository.get_setting", _settings(store)):
        config = repo.get_config()
    assert config["for_all"] is True
    assert config["reveal_round"] == 4


def test_opening_it_for_everyone_starts_a_new_round():
    """A new round brings the invite back for anyone who clicked it away."""
    store = {"evaluation_for_all": "false", "evaluation_reveal_round": "2"}
    with patch("src.features.evaluation.repository.get_setting", _settings(store)), \
         patch("src.features.evaluation.repository.set_setting", _writer(store)):
        repo.set_for_all(True)
    assert store["evaluation_for_all"] == "true"
    assert store["evaluation_reveal_round"] == "3"


def test_closing_it_again_keeps_the_round():
    store = {"evaluation_for_all": "true", "evaluation_reveal_round": "2"}
    with patch("src.features.evaluation.repository.get_setting", _settings(store)), \
         patch("src.features.evaluation.repository.set_setting", _writer(store)):
        repo.set_for_all(False)
    assert store["evaluation_reveal_round"] == "2"


def test_saving_the_switch_that_was_already_on_keeps_the_round():
    """Otherwise a second click on an on switch would pester everyone again."""
    store = {"evaluation_for_all": "true", "evaluation_reveal_round": "2"}
    with patch("src.features.evaluation.repository.get_setting", _settings(store)), \
         patch("src.features.evaluation.repository.set_setting", _writer(store)):
        repo.set_for_all(True)
    assert store["evaluation_reveal_round"] == "2"


def test_switching_the_evaluation_on_starts_a_new_round_too():
    store = {"evaluation_active": "false", "evaluation_reveal_round": "0"}
    with patch("src.features.evaluation.repository.get_setting", _settings(store)), \
         patch("src.features.evaluation.repository.set_setting", _writer(store)):
        repo.set_active(True)
    assert store["evaluation_active"] == "true"
    assert store["evaluation_reveal_round"] == "1"
