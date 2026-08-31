"""The code cuts the gap, the model delivers sentence plus excerpt."""

from src.features.ai_assistant.tasks.language_training._source_grammar import (
    GAP,
    cut_gap,
    is_usable_cloze,
    names_the_form,
)


_SATZ = "Die Messwerte werden vom Server gespeichert."


def test_code_schneidet_die_luecke():
    assert cut_gap(_SATZ, "werden") == "Die Messwerte ___ vom Server gespeichert."


def test_gefuellte_luecke_ergibt_wieder_den_satz():
    """The promise this rework is about, on the reported sentence."""
    satz = "Die Familienmitglieder müssen am Wochenende getroffen werden."
    luecke = cut_gap(satz, "müssen")
    assert luecke.replace(GAP, "müssen") == satz


def test_ausschnitt_der_nicht_drinsteht_faellt_durch():
    assert cut_gap(_SATZ, "wurden") is None


def test_mehrfacher_ausschnitt_faellt_durch():
    """Replaced twice would be two gaps and one solution."""
    assert cut_gap("Der Bericht wird geschrieben und wird gelesen.", "wird") is None


def test_ganzer_satz_als_ausschnitt_faellt_durch():
    assert cut_gap(_SATZ, _SATZ) is None


def test_zu_langer_ausschnitt_faellt_durch():
    """A gap takes a form, the word boundary is the outer limit."""
    satz = "Die Messwerte werden vom Server dauerhaft gespeichert."
    assert cut_gap(satz, "werden vom Server dauerhaft gespeichert") is None


def test_rest_muss_ein_satz_bleiben():
    assert cut_gap("Alles wird gut.", "wird gut") is None


def test_leerer_ausschnitt_faellt_durch():
    assert cut_gap(_SATZ, "") is None


def test_luecke_mit_ausschnitt_ist_brauchbar():
    assert is_usable_cloze(_SATZ, "werden")


def test_satz_der_die_luecke_schon_mitbringt_faellt_durch():
    """Legacy: the prompt now orders the complete sentence."""
    assert not is_usable_cloze("Die Messwerte ___ gespeichert.", "werden")


def test_vier_woerter_bleiben_erlaubt():
    """There are real four-word forms, the limit must not cut them off."""
    assert is_usable_cloze(
        "Der Bericht hätte geschrieben werden können.", "hätte geschrieben werden können")


def test_satz_der_die_zielform_nennt_faellt_durch():
    """Reported: a statement about the grammar instead of an exercise in it."""
    assert names_the_form("Das Verb steht im Relativsatz immer am Ende.",
                          "Relativsatz im Genitiv")


def test_zweiter_gemeldeter_regelsatz_faellt_durch():
    """Reported, the same construction in a gapped sentence."""
    assert names_the_form("Im Passiv muss das Subjekt 'man' weggelassen werden.",
                          "Passiv Modalverb Präsens")


def test_echter_uebungssatz_bleibt():
    assert not names_the_form("Die Messwerte werden vom Server gespeichert.",
                              "Passiv Präsens")


def test_kurze_woerter_im_themennamen_werden_nicht_geprueft():
    """For a topic of everyday words the check simply does not apply."""
    assert not names_the_form("Wir haben keine Zeit.", "haben und sein")


def test_zielform_mitten_im_wort_zaehlt_nicht():
    """Words are compared, not character sequences."""
    assert not names_the_form("Der Kompass zeigt nach Norden.", "Passiv Präsens")
