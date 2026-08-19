"""Die Absage steht am ENDE der Antwort, nicht mehr am Anfang.

Bis 2026-08-16 eroeffnete jede Absage mit demselben Satz und der Hinweis auf das, was
die Quellen doch hergeben, kam danach. Das las sich als Widerspruch im selben Atemzug:
"Diese Information ist nicht in den bereitgestellten Quellen enthalten. Die Quellen
nennen die Komplementaermenge als einen der Grundbegriffe der Mengenlehre." Also erst
nichts gefunden, dann doch etwas.

Seither zuerst die Aussage, zuletzt die Luecke. Drei Regeln tragen das, jede einzeln
gemessen (je 5 Laeufe, gleiches Modell, gleiche Quelle):

* Reihenfolge umdrehen. Loest nebenbei ein zweites Problem: ein Absagesatz VORNE ist so
  verlockend, dass das Modell ihn auch schrieb, wenn die Definition im Kontext stand
  (0/5 richtig). Steht vorne eine normale Aussage, antwortet es (5/5).
* Der Schlusssatz darf nicht abstreiten, was der Satz davor gerade gab. Ohne die Regel
  kam "Die Komplementaermenge ist die Menge aller Elemente ... Was sie genau ist,
  erklaeren die Quellen nicht" (0/5). Mit ihr 5/5 sauber.
* Bei einer Frage nach dem WAS ist der Schlusssatz Pflicht. Ohne diesen Zusatz liess das
  Modell ihn weg und nannte nur die Fundstelle (3/5), dann haelt der Leser eine blosse
  Erwaehnung fuer die Antwort.
"""
import pytest

from src.services.aia_adaptive_chat import ADAPTIVE_SOURCES_GUARD
from src.features.ai_assistant.prompts.rag_chat import aia_system_rag
from src.features.ai_assistant.prompts.refusal_prompts import (
    RAG_NO_INFO_SENTINEL,
    is_gap_line,
    is_sentinel_refusal,
    refusal_reference_texts,
)


# ── der Prompt schreibt die Reihenfolge vor ──────────────────────────────────

def test_prompt_trennt_die_absage_in_ein_eigenes_feld():
    """Der Satz ueber das Fehlende steht in "gap", damit er nie einen Chip bekommt."""
    p = aia_system_rag("de")
    assert "## Answer format" in p
    for feld in ('"gap"', '"items"', '"body"'):
        assert feld in p
    assert "belongs in \"gap\" alone" in p
    assert RAG_NO_INFO_SENTINEL["de"] not in p



def test_guard_beschreibt_keine_antwortform_mehr():
    """Die Form steht nur noch im Hauptprompt, sonst widersprechen sich beide."""
    for satz in ("gap sentence", "Never open with a bare refusal", "goes last"):
        assert satz not in ADAPTIVE_SOURCES_GUARD
    assert "decided by the system prompt alone" in ADAPTIVE_SOURCES_GUARD


# ── Schnellpfad: nur die alleinstehende Absage ist eine reine Absage ─────────

@pytest.mark.parametrize("locale", ["de", "en"])
def test_old_opening_sentence_still_counts(locale):
    """Antworten aus dem Verlauf tragen ihn noch."""
    assert is_sentinel_refusal(RAG_NO_INFO_SENTINEL[locale]) is True


def test_old_opening_sentence_survives_bold_and_a_missing_period():
    assert is_sentinel_refusal(
        "**Diese Information ist nicht in den bereitgestellten Quellen enthalten**") is True


@pytest.mark.parametrize("answer", [
    "Der Wechselkurs von Bitcoin steht nicht in den Quellen.",
    "Was die Komplementärmenge bedeutet, steht nicht in den Quellen.",
    "The exchange rate is not in the sources.",
])
def test_standalone_gap_sentence_counts_as_a_pure_refusal(answer):
    assert is_sentinel_refusal(answer) is True


def test_statement_plus_gap_sentence_is_not_a_pure_refusal():
    """Der ERSTE Satz nennt etwas, das wirklich dasteht, und braucht seinen Chip.

    Wuerde der Schnellpfad hier zugreifen, uebersprænge er die ganze Chip-Suche und
    der Satz verlöre seine Quellenangabe."""
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


# ── Referenzsaetze fuer die Erkennung per Einbettung ─────────────────────────

def test_reference_texts_stay_at_the_old_sentence_only():
    """Die heutige Bauform gehoert NICHT in die Referenzliste.

    Gemessen 2026-08-16: nimmt man sie auf, rutscht der Aussagesatz davor ("Die Quellen
    nennen eine Klausur ... und geben Hinweise dazu") von 0,62 auf 0,551 und faellt unter
    die Schwelle von 0,60. Er verlöre damit seinen Quellenchip, obwohl er etwas nennt,
    das wirklich in den Quellen steht. Ein Satz UEBER die Quellen und ein Satz ueber eine
    LUECKE in den Quellen liegen zu dicht beieinander, darum entscheidet hier Text und
    nicht Abstand."""
    texts = refusal_reference_texts()
    assert sorted(texts) == sorted(RAG_NO_INFO_SENTINEL.values())


# ── der Absage-Satz wird woertlich erkannt ──────────────────────────────────

@pytest.mark.parametrize("line", [
    "Wann die Klausur ist, steht nicht in den Quellen.",
    "Was die Komplementärmenge bedeutet, steht nicht in den Quellen.",
    "Der Wechselkurs von Bitcoin steht nicht in den Quellen.",
    "Die genauen Uhrzeiten stehen nicht in den Quellen.",
    "When the exam takes place is not in the sources.",
    "The exact times are not in the sources.",
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
    """Diese Saetze BRAUCHEN ihren Chip, er ist die Navigation zur Fundstelle."""
    assert is_gap_line(line) is False


def test_gap_line_survives_bold():
    assert is_gap_line("**Wann die Klausur ist**, steht nicht in den Quellen.") is True


def test_prompt_keeps_one_fact_per_sentence_in_the_opening():
    """Zwei Funde aus zwei Quellen sind ZWEI Saetze, nicht einer.

    Der Prompt sagte "OPEN with ... ONE short sentence with its concrete facts" und
    zwang damit zwei Funde in einen Satz. Die Chip-Vergabe arbeitet aber pro Satz und
    sucht die Fundstelle fuer den ganzen Satz. Ein Satz ueber zwei Passagen laesst sich
    keiner von beiden zuordnen. Beobachtet am 2026-08-16 auf Produktion: "Die Quellen
    erwaehnen eine Klausur 8.9. sowie die Feststellung der Pruefungsvorleistung bis zum
    15. Juni" bekam drei Chips, und die Aufzeichnung mit dem 8.9. war bei keinem dabei.
    Genau die haette der Leser gebraucht, denn dort zeigt der Dozent eine ALTE Klausur.
    """
    p = aia_system_rag("de")
    assert "ONE FACT PER SENTENCE" in p
    # Die alte Vorgabe darf nicht zurueckkommen.
    assert "OPEN with what the documents DO say about the subject, ONE short sentence" not in p


# ENTFALLEN mit der Kurzfassung des Prompts (2026-08-19): "NAME THE MISSING PIECE
# EXACTLY", "NEVER by echoing the question back" und die Gegenprobe "If the second
# one seems to take back the first". Anlass war der 2026-08-16: der Satz davor nannte
# eine Klausur vom 8.9., die Absage warf die Frage nur zurueck ("wann die Klausur
# ist") und las sich wie ein Widerspruch, obwohl die 8.9. eine ALTE Klausur war.
