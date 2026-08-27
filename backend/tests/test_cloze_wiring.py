"""The cloze uses the pool only when generated from the sources."""

from src.features.ai_assistant.repository.stats import LANGUAGE_TRAINING_TOOLS
from src.features.ai_assistant.schemas import CreateSetBody
from src.features.ai_assistant.tasks.language_training._pool import POOL_TOOLS, uses_pool
from src.features.ai_assistant.tasks.language_training._source_cloze import (
    usable_flashcard_set,
)


def test_aus_quellen_laeuft_ueber_den_vorrat():
    assert "wortschatz" in POOL_TOOLS
    assert uses_pool("wortschatz", "source") is True


def test_aus_lernkarten_laeuft_nicht_ueber_den_vorrat():
    # The card path is mode='cards' and therefore falls out of the pool.
    assert uses_pool("wortschatz", "cards") is False


def test_der_lueckentext_zaehlt_zum_sprachtrainer():
    assert "wortschatz" in LANGUAGE_TRAINING_TOOLS


def test_die_anfrage_kann_ein_lernkarten_set_nennen():
    body = CreateSetBody(tool="wortschatz", mode="cards", count=10, flashcard_set_id=42)
    assert body.flashcard_set_id == 42


def test_ohne_lernkarten_set_bleibt_das_feld_leer():
    body = CreateSetBody(tool="grammatik", mode="source", count=10)
    assert body.flashcard_set_id is None


_FREMD = {"id": 3, "workspace_id": 99, "user_id": 1, "tool": "flashcards", "status": "ready"}
_EIGEN = {"id": 3, "workspace_id": 7, "user_id": 1, "tool": "flashcards", "status": "ready"}


def test_ein_eigenes_fertiges_lernkarten_set_wird_angenommen():
    assert usable_flashcard_set(_EIGEN, workspace_id=7, user_id=1) is True


def test_ein_set_aus_einem_fremden_kursraum_wird_abgelehnt():
    assert usable_flashcard_set(_FREMD, workspace_id=7, user_id=1) is False


def test_ein_set_einer_anderen_person_wird_abgelehnt():
    assert usable_flashcard_set(_EIGEN, workspace_id=7, user_id=2) is False


def test_ein_set_eines_anderen_werkzeugs_wird_abgelehnt():
    quiz = dict(_EIGEN, tool="quiz")
    assert usable_flashcard_set(quiz, workspace_id=7, user_id=1) is False


def test_ein_noch_entstehender_satz_wird_abgelehnt():
    # A set without finished cards has no words to give.
    roh = dict(_EIGEN, status="generating")
    assert usable_flashcard_set(roh, workspace_id=7, user_id=1) is False


def test_gar_kein_set_wird_abgelehnt():
    assert usable_flashcard_set(None, workspace_id=7, user_id=1) is False
