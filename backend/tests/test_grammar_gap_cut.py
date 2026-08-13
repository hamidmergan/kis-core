"""Die Lücke schneidet der Code, nicht das Modell.

Bis zum 2026-08-12 lieferte das Modell den Satz mit der Lücke schon darin und dazu,
was hineingehört. Es entschied damit selbst, wie viel es herausnimmt, und vier der
sechs Meldungen von diesem Tag entstanden genau dabei:

* "Man benutzt ___ Handfeuerlöscher zur Brandbekämpfung." mit "einen Handfeuerlöscher"
  als Lösung. Das Nomen stand dann zweimal da.
* "Das Gebäude hat ___ sicheres Rettungssystem." mit "ein sicheres Rettungssystem".
* "Die Familienmitglieder ___ am Wochenende treffen." mit "müssen getroffen werden".
  Hinten blieb "treffen" stehen, der Satz war unlesbar.
* "Im Passiv ___ das Subjekt 'man' ___." Zwei Lücken, eine Lösung.

Jetzt liefert das Modell den VOLLSTÄNDIGEN Satz und dazu den Ausschnitt, der die
Zielform trägt. Geschnitten wird im Code. Damit ergibt die gefüllte Lücke wieder genau
den Ausgangssatz, und keiner der vier Fehler ist mehr formulierbar. Kein Urteil, keine
Wortliste, nur eine Zeichenprüfung.

Kein DB- und kein Netzzugriff.
"""

from src.features.ai_assistant.tasks.language_training._source_grammar import (
    GAP,
    cut_gap,
    is_usable_cloze,
    names_the_form,
)


_SATZ = "Die Messwerte werden vom Server gespeichert."
_OPTIONEN = ["werden", "wird", "worden", "waren"]


def test_code_schneidet_die_luecke():
    assert cut_gap(_SATZ, "werden") == "Die Messwerte ___ vom Server gespeichert."


def test_gefuellte_luecke_ergibt_wieder_den_satz():
    """Die Zusage, um die es bei diesem Umbau geht, an YS' Satz aus Meldung 5."""
    satz = "Die Familienmitglieder müssen am Wochenende getroffen werden."
    luecke = cut_gap(satz, "müssen")
    assert luecke.replace(GAP, "müssen") == satz


def test_ausschnitt_der_nicht_drinsteht_faellt_durch():
    assert cut_gap(_SATZ, "wurden") is None


def test_mehrfacher_ausschnitt_faellt_durch():
    """Zweimal ersetzt wären zwei Lücken und eine Lösung, YS' Meldung 6."""
    assert cut_gap("Der Bericht wird geschrieben und wird gelesen.", "wird") is None


def test_ganzer_satz_als_ausschnitt_faellt_durch():
    assert cut_gap(_SATZ, _SATZ) is None


def test_zu_langer_ausschnitt_faellt_durch():
    """In eine Lücke gehört eine Form, nicht der halbe Satz.

    Die Grenze liegt bei vier Wörtern, weil es echte Formen aus vier Wörtern gibt. Sie
    ist nur die äussere Schranke, eine zu grosse Lücke erkennt die Optionsregel in
    ``is_usable_cloze``.
    """
    satz = "Die Messwerte werden vom Server dauerhaft gespeichert."
    assert cut_gap(satz, "werden vom Server dauerhaft gespeichert") is None


def test_rest_muss_ein_satz_bleiben():
    assert cut_gap("Alles wird gut.", "wird gut") is None


def test_leerer_ausschnitt_faellt_durch():
    assert cut_gap(_SATZ, "") is None


def test_luecke_mit_ausschnitt_ist_brauchbar():
    assert is_usable_cloze(_SATZ, "werden", _OPTIONEN, 0)


def test_markierte_option_muss_der_ausschnitt_sein():
    assert not is_usable_cloze(_SATZ, "werden", _OPTIONEN, 1)


def test_vier_optionen_sind_pflicht():
    assert not is_usable_cloze(_SATZ, "werden", ["werden", "wird"], 0)


def test_zweimal_dieselbe_option_faellt_durch():
    assert not is_usable_cloze(_SATZ, "werden", ["werden", "Werden", "wird", "waren"], 0)


def test_satz_der_die_luecke_schon_mitbringt_faellt_durch():
    """Alte Ware: der Prompt bestellt jetzt den vollständigen Satz."""
    assert not is_usable_cloze("Die Messwerte ___ gespeichert.", "werden", _OPTIONEN, 0)


def test_wort_in_allen_vier_optionen_faellt_durch():
    """YS' Meldung 3: die Lücke schluckte das Nomen mit.

    Ein Wort, das in ALLEN vier Optionen steht, ist nicht die geübte Form, sondern
    Zusammenhang. Der gehört in den Satz und nicht in die Lücke. Ohne diese Regel käme
    "Das Gebäude hat ___." mit "ein sicheres Rettungssystem" als Option heraus: formal
    heil, aber es übt die Adjektivendung nicht mehr.
    """
    assert not is_usable_cloze(
        "Das Gebäude hat ein sicheres Rettungssystem.", "ein sicheres Rettungssystem",
        ["ein sicheres Rettungssystem", "einen sicheren Rettungssystem",
         "ein sicher Rettungssystem", "einer sichere Rettungssystem"], 0)


def test_gemeldeter_handfeuerloescher_faellt_durch():
    """YS' Meldung 2, dieselbe Bauart."""
    assert not is_usable_cloze(
        "Man benutzt einen Handfeuerlöscher zur Brandbekämpfung.",
        "einen Handfeuerlöscher",
        ["einen Handfeuerlöscher", "ein Handfeuerlöscher",
         "einem Handfeuerlöscher", "einer Handfeuerlöscher"], 0)


def test_teilweise_gemeinsame_woerter_sind_erlaubt():
    """Vier Formen einer Verbgruppe teilen sich Wörter, aber keines steht in allen vier.

    Das ist der Unterschied zur geschluckten Lücke, und deshalb ist die Regel "in ALLEN
    vier" und nicht "in mehr als einer".
    """
    assert is_usable_cloze(
        "Die Angabe muss weggelassen werden.", "muss weggelassen werden",
        ["muss weggelassen werden", "wird weglassen",
         "muss weglassen", "soll weggelassen sein"], 0)


def test_vier_woerter_bleiben_erlaubt():
    """Es gibt echte Formen aus vier Wörtern, die Grenze darf sie nicht abschneiden."""
    assert is_usable_cloze(
        "Der Bericht hätte geschrieben werden können.", "hätte geschrieben werden können",
        ["hätte geschrieben werden können", "wäre geschrieben worden",
         "hat schreiben können", "würde schreiben können"], 0)


def test_satz_der_die_zielform_nennt_faellt_durch():
    """YS' Meldung 4: eine Aussage über die Grammatik statt einer Übung in ihr."""
    assert names_the_form("Das Verb steht im Relativsatz immer am Ende.",
                          "Relativsatz im Genitiv")


def test_zweiter_gemeldeter_regelsatz_faellt_durch():
    """YS' Meldung 6, dieselbe Bauart in einem Lückensatz."""
    assert names_the_form("Im Passiv muss das Subjekt 'man' weggelassen werden.",
                          "Passiv Modalverb Präsens")


def test_echter_uebungssatz_bleibt():
    assert not names_the_form("Die Messwerte werden vom Server gespeichert.",
                              "Passiv Präsens")


def test_kurze_woerter_im_themennamen_werden_nicht_geprueft():
    """Ein Thema kann nach Alltagswörtern heissen.

    Dann greift die Prüfung eben nicht, statt jeden Übungssatz des Themas zu
    verwerfen. Lieber kein Schutz für ein Thema als kein Set.
    """
    assert not names_the_form("Wir haben keine Zeit.", "haben und sein")


def test_zielform_mitten_im_wort_zaehlt_nicht():
    """Verglichen werden Wörter, nicht Zeichenfolgen.

    Sonst würde "passiv" in "kompassiv..." treffen, und mit Beugung wäre kein Satz
    mehr sicher.
    """
    assert not names_the_form("Der Kompass zeigt nach Norden.", "Passiv Präsens")
