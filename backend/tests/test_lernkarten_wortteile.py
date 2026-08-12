"""Die Wortzerlegung auf der Lernkarte wird nachgerechnet, nicht geglaubt.

Das Modell hat "Einstieg" zu "einsteigen + leg" zerlegt und "leg" als "Endung fuer den
Vorgang" erklaert. Beides steht so im Prompt verboten, aber ein Prompt ist eine Bitte.
Hier steht die Rechnung dazu: ein Teil, der im Begriff gar nicht vorkommt, kippt die
ganze Zerlegung.

Die Pruefung kennt keine deutschen Wortlisten. Sie vergleicht nur Buchstaben, damit sie
in jeder Sprache dasselbe tut.
"""

import json
import types

from src.features.ai_assistant.tasks.language_training._glossary import _generate_flashcards
from src.features.ai_assistant.tasks.language_training._source_flashcards import (
    _format_lernkarte,
)
from src.features.ai_assistant.tasks.language_training._wortteile import clean_word_parts


def _fake_client(content: str):
    """Modell-Ersatz: liefert immer dieselbe Antwort, kein Netz, keine Datenbank."""
    def create(model, messages, **kwargs):
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )


# --- was rausfliegt ----------------------------------------------------------

def test_erfundener_teil_kippt_die_ganze_zerlegung():
    """Der Fall aus der Karte: 'leg' steckt nirgends in 'Einstieg'."""
    parts, explained = clean_word_parts(
        "Einstieg", "einsteigen + leg",
        "einsteigen = in etwas hineingehen | der leg = Endung fuer den Vorgang",
    )
    assert parts == ""
    assert explained == ""


def test_ableitung_mit_ablaut_ist_kein_kompositum():
    """'steigen' wird zu 'stieg', der Wortstamm steht also nicht im Begriff."""
    parts, _ = clean_word_parts("Einstieg", "ein + steigen", "")
    assert parts == ""


def test_ein_einziger_teil_ist_keine_zerlegung():
    parts, explained = clean_word_parts("Bildung", "Bildung", "die Bildung = das Lernen")
    assert (parts, explained) == ("", "")


def test_erklaerung_ohne_teile_verschwindet():
    """Die Ansicht zeigt den Kasten nur mit Teilen. Eine Erklaerung ohne sie ist Datenmuell."""
    _, explained = clean_word_parts("Wirksamkeit", "", "die Keit = eine Endung")
    assert explained == ""


def test_ein_kaputter_teil_reicht_zum_verwerfen():
    parts, _ = clean_word_parts("Brandverhuetung", "Brand + Verhuetung + keit", "")
    assert parts == ""


# --- was bleibt --------------------------------------------------------------

def test_echtes_kompositum_bleibt_unveraendert():
    parts, explained = clean_word_parts(
        "Studienabbruchquote", "Studien + Abbruch + Quote",
        "die Studien = die Zeit an der Uni | der Abbruch = das vorzeitige Ende "
        "| die Quote = ein Anteil",
    )
    assert parts == "Studien + Abbruch + Quote"
    assert explained.startswith("die Studien =")


def test_fugenlaut_darf_fehlen():
    """'Hilfsverb' zu 'Hilfe + Verb' ist die verlangte Grundform, kein Fehler."""
    parts, _ = clean_word_parts("Hilfsverb", "Hilfe + Verb", "")
    assert parts == "Hilfe + Verb"


def test_plural_wird_zur_einzahl_und_bleibt_gueltig():
    parts, _ = clean_word_parts("Passivsätze", "Passiv + Satz", "")
    assert parts == "Passiv + Satz"


def test_umlaut_und_kleinschreibung_stoeren_nicht():
    parts, _ = clean_word_parts("Primärliteratur", "primär + Literatur", "")
    assert parts == "primär + Literatur"


def test_mehrwortbegriff_bleibt_zerlegbar():
    parts, _ = clean_word_parts(
        "zulassungspflichtiges Handwerk", "Zulassung + pflichtig + Handwerk", "")
    assert parts == "Zulassung + pflichtig + Handwerk"


def test_scharfes_s_bleibt_gueltig():
    parts, _ = clean_word_parts("Straßenbahn", "Straße + Bahn", "")
    assert parts == "Straße + Bahn"


# --- die Erklaerung zu den Teilen --------------------------------------------

def test_artikel_vor_dem_teil_stoert_die_zuordnung_nicht():
    _, explained = clean_word_parts(
        "Inhaltsverzeichnis", "Inhalt + Verzeichnis",
        "der Inhalt = das, was im Text steht | das Verzeichnis = eine Liste",
    )
    assert explained == "der Inhalt = das, was im Text steht | das Verzeichnis = eine Liste"


def test_erklaerung_zum_falschen_wort_faellt_weg_die_teile_bleiben():
    """Die Teile stimmen, die Erklaerung redet von etwas anderem."""
    parts, explained = clean_word_parts(
        "Pufferzeit", "Puffer + Zeit", "der Schnee = weisses Eis | die Zeit = die Dauer")
    assert parts == "Puffer + Zeit"
    assert explained == ""


def test_fehlende_erklaerung_zu_einem_teil_faellt_weg():
    parts, explained = clean_word_parts(
        "Studienabbruchquote", "Studien + Abbruch + Quote",
        "die Studien = die Zeit an der Uni | der Abbruch = das Ende")
    assert parts == "Studien + Abbruch + Quote"
    assert explained == ""


def test_leere_eingabe_bleibt_leer():
    assert clean_word_parts("Einstieg", "", "") == ("", "")


# --- die Verdrahtung: beide Wege zur Lernkarte gehen durch die Pruefung -------

def test_karte_aus_der_quelle_verliert_die_erfundene_zerlegung():
    item = _format_lernkarte({
        "begriff": "Einstieg",
        "definition": "Der Beginn einer neuen Aktivität.",
        "word_parts": "einsteigen + leg",
        "word_parts_explained": "einsteigen = hineingehen | der leg = Endung für den Vorgang",
        "word_class": "Nomen",
    })
    assert "word_parts" not in item["extras"]
    assert "word_parts_explained" not in item["extras"]
    # Der Rest der Karte bleibt stehen, verworfen wird nur der Kasten.
    assert item["extras"]["word_class"] == "Nomen"
    assert item["back"] == "Der Beginn einer neuen Aktivität."


def test_karte_aus_der_quelle_behaelt_die_richtige_zerlegung():
    item = _format_lernkarte({
        "begriff": "Pufferzeit",
        "definition": "Zeit als Reserve.",
        "word_parts": "Puffer + Zeit",
        "word_parts_explained": "der Puffer = ein Schutzraum | die Zeit = die Dauer",
    })
    assert item["extras"]["word_parts"] == "Puffer + Zeit"


def test_karte_aus_dem_glossar_verliert_die_erfundene_zerlegung():
    antwort = json.dumps({"cards": [{
        "begriff": "Einstieg",
        "definition": "Der Beginn einer neuen Aktivität.",
        "word_parts": "einsteigen + leg",
        "word_parts_explained": "einsteigen = hineingehen | der leg = Endung für den Vorgang",
        "word_class": "Nomen",
    }]})
    client = _fake_client(antwort)
    eintraege = [{"term_de": "Einstieg", "term_en": "start", "definition": "Der Beginn.",
                  "filename": "Studienstart.pdf", "page_number": 3}]

    items = _generate_flashcards(client, "modell", eintraege, "German")

    assert "word_parts" not in items[0].get("extras", {})
    assert items[0]["extras"]["word_class"] == "Nomen"
