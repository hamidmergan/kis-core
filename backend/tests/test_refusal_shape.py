"""The refusal comes at the end of the answer, three measured rules carry that."""
import pytest

from src.services.aia_adaptive_chat import ADAPTIVE_SOURCES_GUARD
from src.features.ai_assistant.prompts.rag_chat import aia_system_rag
from src.features.ai_assistant.prompts.refusal_prompts import (
    RAG_NO_INFO_SENTINEL,
    is_gap_line,
    is_only_gap,
    is_sentinel_refusal,
    refusal_reference_texts,
)


# ── the prompt prescribes the order ──────────────────────────────────────────

def test_prompt_trennt_die_absage_in_ein_eigenes_feld():
    """The sentence about what is missing sits in 'no_info_sentence' so it never gets a chip."""
    p = aia_system_rag("de")
    assert "## Answer format" in p
    for feld in ('"no_info_sentence"', '"items"', '"body"'):
        assert feld in p
    assert "belongs in \"no_info_sentence\" alone" in p
    assert RAG_NO_INFO_SENTINEL["de"] not in p



def test_guard_beschreibt_keine_antwortform_mehr():
    """The shape lives in the main prompt only, otherwise the two contradict each other."""
    for satz in ("gap sentence", "Never open with a bare refusal", "goes last"):
        assert satz not in ADAPTIVE_SOURCES_GUARD
    assert "decided by the system prompt alone" in ADAPTIVE_SOURCES_GUARD


# ── Fast path: only the standalone refusal is a pure refusal ─────────────────

def test_old_opening_sentence_still_counts():
    """Answers from the history still carry it."""
    assert is_sentinel_refusal(RAG_NO_INFO_SENTINEL["de"]) is True


def test_old_opening_sentence_survives_bold_and_a_missing_period():
    assert is_sentinel_refusal(
        "**Diese Information ist nicht in den bereitgestellten Materialien enthalten**") is True


@pytest.mark.parametrize("answer", [
    "Der Wechselkurs von Bitcoin steht nicht in den Materialien.",
    "Was die Komplementärmenge bedeutet, steht nicht in den Materialien.",
    "Der Wechselkurs von Bitcoin steht nicht in den Quellen.",
    "Was die Komplementärmenge bedeutet, steht nicht in den Quellen.",
])
def test_standalone_gap_sentence_counts_as_a_pure_refusal(answer):
    assert is_sentinel_refusal(answer) is True


def test_statement_plus_gap_sentence_is_not_a_pure_refusal():
    """The first sentence names something that exists and needs its chip."""
    assert is_sentinel_refusal(
        "Die Quellen beschreiben als Prüfungsleistung eine Hausarbeit von sechs bis "
        "sieben Seiten mit Abgabe am 3. Juli. Wann die Klausur ist, steht nicht in den Quellen."
    ) is False


def test_old_sentence_plus_pointer_is_not_a_pure_refusal():
    assert is_sentinel_refusal(
        RAG_NO_INFO_SENTINEL["de"] + " Die Quellen beschreiben stattdessen eine Hausarbeit."
    ) is False


def test_a_real_answer_is_not_a_refusal():
    assert is_sentinel_refusal(
        "Die Komplementärmenge ist die Menge aller Elemente, die nicht zu A gehören."
    ) is False


def test_empty_is_not_a_refusal():
    assert is_sentinel_refusal("") is False
    assert is_sentinel_refusal(None) is False


# ── Reference sentences for detection by embedding ───────────────────────────

def test_reference_texts_stay_at_the_old_sentence_only():
    """The current construction does not belong in the reference list, otherwise the claim fails."""
    texts = refusal_reference_texts()
    assert RAG_NO_INFO_SENTINEL["de"] in texts


def test_reference_texts_measure_against_german_alone():
    """One anchor is enough, a second catches nothing extra and causes false alarms."""
    assert refusal_reference_texts() == [RAG_NO_INFO_SENTINEL["de"]]
    assert list(RAG_NO_INFO_SENTINEL) == ["de"]


# ── the refusal sentence is matched verbatim ────────────────────────────────

@pytest.mark.parametrize("line", [
    "Wann die Klausur ist, steht nicht in den Quellen.",
    "Was die Komplementärmenge bedeutet, steht nicht in den Quellen.",
    "Der Wechselkurs von Bitcoin steht nicht in den Materialien.",
    "Was die Komplementärmenge bedeutet, steht nicht in den Materialien.",
    "Der Wechselkurs von Bitcoin steht nicht in den Quellen.",
    "Die genauen Uhrzeiten stehen nicht in den Quellen.",
])
def test_gap_line_is_recognised(line):
    assert is_gap_line(line) is True


@pytest.mark.parametrize("line", [
    "Die Quellen nennen eine Klausur für das Modul Multimediatechnik und geben Hinweise dazu.",
    "Die Quellen führen die Komplementärmenge im Kapitel über Mengenverknüpfungen auf.",
    "Die Komplementärmenge ist die Menge aller Elemente, die nicht zu A gehören.",
    "Die Abgabe ist am 3. Juli.",
    "",
])
def test_a_statement_about_the_sources_is_not_a_gap_line(line):
    """These sentences NEED their chip, it is the navigation to the spot."""
    assert is_gap_line(line) is False


def test_gap_line_survives_bold():
    assert is_gap_line("**Wann die Klausur ist**, steht nicht in den Quellen.") is True


def test_prompt_keeps_one_fact_per_sentence_in_the_opening():
    """Two findings from two sources are two sentences, otherwise no chip fits."""
    p = aia_system_rag("de")
    assert "ONE FACT PER SENTENCE" in p
    # The old requirement must not come back.
    assert "OPEN with what the documents DO say about the subject, ONE short sentence" not in p




# ── the dedicated field beats guessing from the wording ─────────────────────

def test_only_gap_erkennt_die_reine_absage_am_feld():
    """The model marked the sentence as a refusal itself, there is nothing more."""
    satz = "Wann die Klausur ist, steht nicht in den Materialien."
    assert is_only_gap(satz, satz) is True


def test_only_gap_haelt_in_jeder_sprache():
    """Exactly what the field is for: neither the reference sentence nor an anchor applies here."""
    satz = "Sınav tarihi materyallerde yer almıyor."
    assert is_only_gap(satz, satz) is True
    assert is_sentinel_refusal(satz) is False


def test_only_gap_vertraegt_fettdruck_und_fehlenden_punkt():
    assert is_only_gap(
        "**Wann die Klausur ist, steht nicht in den Materialien**",
        "Wann die Klausur ist, steht nicht in den Materialien.") is True


def test_only_gap_ist_falsch_wenn_die_antwort_weitergeht():
    """Bridge and entries name something real and need their chips."""
    gap = "Wann die Klausur ist, steht nicht in den Materialien"
    assert is_only_gap(
        gap + ", jedoch beschreiben die Materialien die Hausarbeit:\n"
        "- **Umfang**: sechs bis sieben Seiten.",
        gap) is False


def test_only_gap_ohne_feld_ist_falsch():
    """Without the field set the caller falls back to guessing from the wording."""
    assert is_only_gap("Irgendein Satz.", "") is False
    assert is_only_gap("Irgendein Satz.", None) is False
