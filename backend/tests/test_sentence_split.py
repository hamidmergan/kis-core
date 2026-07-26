"""Language-agnostic sentence splitter for per-sentence citation attribution.

Prose answers (NotebookLM style) attach a source chip AFTER EACH SENTENCE, so the
attribution needs sentence boundaries. The splitter favours PRECISION over recall:
a MISSED split just leaves two sentences sharing one chip (the old block behaviour,
no regression), but a FALSE split would drop a chip into the middle of a sentence.
So every guard below suppresses a split when it is not clearly a real boundary.
No language word lists (works for DE, EN, and any Latin-script source).
"""
from src.features.ai_assistant.routes._helpers import _split_sentences


# ── the happy path: real boundaries split ────────────────────────────────────

def test_splits_two_plain_sentences():
    assert _split_sentences("Der Kurs startet im April. Die Abgabe ist im Juli.") == [
        "Der Kurs startet im April.",
        "Die Abgabe ist im Juli.",
    ]


def test_splits_on_question_and_exclamation():
    assert _split_sentences("Was ist Wissenschaft? Das klaert der Kurs!") == [
        "Was ist Wissenschaft?",
        "Das klaert der Kurs!",
    ]


def test_single_sentence_returns_one_unit():
    assert _split_sentences("Nur ein Satz ohne weiteren Punkt dahinter.") == [
        "Nur ein Satz ohne weiteren Punkt dahinter."
    ]


def test_english_sentences_split():
    assert _split_sentences("The deadline is July 3rd. Submit on time.") == [
        "The deadline is July 3rd.",
        "Submit on time.",
    ]


# ── guards: these must NOT split (would put a chip mid-sentence) ──────────────

def test_no_split_on_single_letter_abbreviation_zb():
    # "z. B." (spaced) must stay inside the sentence.
    assert _split_sentences("Nutze Tools wie z. B. Zotero. Das hilft dabei.") == [
        "Nutze Tools wie z. B. Zotero.",
        "Das hilft dabei.",
    ]


def test_no_split_on_page_ref_S():
    # "S. 5" (page ref) must stay intact — no chip lands between "S." and "5". The real
    # boundary is the sentence's own period at "Anhang.". A bare number directly BEFORE a
    # sentence-ending period ("... auf S. 5. Der ...") is deliberately left un-split, since
    # it is locally indistinguishable from an ordinal ("3. Juli"); that is a missed split
    # (two sentences share one chip), never a mid-sentence chip.
    assert _split_sentences("Die Quelle steht auf S. 5 im Anhang. Der Termin folgt.") == [
        "Die Quelle steht auf S. 5 im Anhang.",
        "Der Termin folgt.",
    ]


def test_no_split_on_decimal_number():
    assert _split_sentences("Der Wert liegt bei 6.2 Prozent im Schnitt. Das ist viel.") == [
        "Der Wert liegt bei 6.2 Prozent im Schnitt.",
        "Das ist viel.",
    ]


def test_no_split_on_german_ordinal_date():
    # "am 3. Juli" is one sentence — the digit-before-period guard keeps it together.
    assert _split_sentences("Die Abgabe ist am 3. Juli faellig. Bitte einhalten.") == [
        "Die Abgabe ist am 3. Juli faellig.",
        "Bitte einhalten.",
    ]


def test_no_split_on_capitalized_short_abbreviation():
    # "Prof." / "Dr." are capitalized tokens of length <= 4 -> treated as abbreviations.
    assert _split_sentences("Betreut von Prof. Meyer im Seminar. Kontakt per Mail.") == [
        "Betreut von Prof. Meyer im Seminar.",
        "Kontakt per Mail.",
    ]


def test_no_split_inside_email():
    assert _split_sentences("Schreib an lenka.kleinau@th-luebeck.de. Sie antwortet schnell.") == [
        "Schreib an lenka.kleinau@th-luebeck.de.",
        "Sie antwortet schnell.",
    ]


def test_no_split_on_parenthesized_abbreviation():
    # A leading "(" must not hide the single-letter "z." / "B." abbreviations inside
    # "(z. B. …)". Real case: "Datenbanken (z. B. DBIS, ACM) und Portale." wrongly split at
    # "(z." because the paren stuck to the token. The boundary is only the sentence's period.
    assert _split_sentences("Nutze Datenbanken (z. B. DBIS und ACM) im Katalog. Das hilft dabei.") == [
        "Nutze Datenbanken (z. B. DBIS und ACM) im Katalog.",
        "Das hilft dabei.",
    ]


def test_no_split_on_dotted_abbreviation_ua():
    # "u.a." (no spaces) contains an internal period -> abbreviation, no split before "Zotero".
    assert _split_sentences("Genutzt werden u.a. Zotero und Citavi. Beide sind gut.") == [
        "Genutzt werden u.a. Zotero und Citavi.",
        "Beide sind gut.",
    ]


# ── shape / robustness ───────────────────────────────────────────────────────

def test_no_boundary_returns_text_unchanged():
    assert _split_sentences("Ein Fragment ohne Satzende") == ["Ein Fragment ohne Satzende"]


def test_empty_string_returns_empty_list():
    assert _split_sentences("   ") == []


def test_join_reconstructs_prose_with_single_spaces():
    text = "Erster Satz hier. Zweiter Satz dort. Dritter Satz da."
    assert " ".join(_split_sentences(text)) == text
