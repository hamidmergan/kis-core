"""Der Satz ueber das Fehlende geht so heraus, wie das Modell ihn geschrieben hat.

Bis 2026-08-21 baute der Code einen Satz drumherum, wenn im Feld nur ein Begriff stand,
und tauschte ein Bindewort aus der falschen Sprache aus. Beides ging nur auf Deutsch und
Englisch, und beides schrieb bei einer tuerkischen oder spanischen Frage einen deutschen
Satz in die Antwort.

Die Ursache lag nicht im Zusammenbau, sondern in der Anweisung an das Modell: das Feld
hiess "gap" und lud damit zu einem Wort statt zu einem Satz ein, im Formular stand keine
Regel am Feld, der Absatz widersprach sich ("NEVER the bare term" gegen "NAME ... BY THE
QUESTION'S OWN WORD"), und die zwei Bindewoerter standen als Beispiel nebeneinander.

Nach der Korrektur an diesen vier Stellen sprang die Reparatur in 26 echten Aufrufen
ueber vier Sprachen kein einziges Mal an. Sie ist darum geloescht. Was bleibt, ist eine
Meldung im Log, falls das Modell doch wieder nur einen Begriff schreibt.
"""

from src.features.ai_assistant.routes._json_stream import AntwortStrom


def _lies(roh: str, **kw) -> str:
    strom = AntwortStrom(**kw)
    return "".join(strom.feed(z) for z in roh)


def _antwort(gap: str, bridge: str, items: str = '{"term": "T", "text": "S."}') -> str:
    return (
        '{"no_info_sentence": "' + gap + '", "bridge": "' + bridge + '", '
        '"items": [' + items + '], "body": ""}'
    )


# -- Der Text des Modells bleibt der Text des Modells ---------------------------

def test_ganzer_satz_bleibt_wie_er_ist():
    gap = "Die Unterlagen nennen keine „Folien“."
    text = _lies(_antwort(gap, "jedoch wird die Präsentation übertragen"))
    assert text.startswith("Die Unterlagen nennen keine „Folien“, jedoch wird")


def test_nackter_begriff_bekommt_keinen_deutschen_rahmen():
    """Frueher baute der Code hier einen deutschen Satz drumherum."""
    text = _lies(_antwort("Folien", "jedoch wird die Präsentation übertragen"))
    assert text.startswith("Folien, jedoch wird die Präsentation übertragen:")
    assert "In den Materialien steht nichts" not in text


def test_tuerkischer_begriff_bleibt_tuerkisch():
    """Genau dieser Fall lieferte vorher Deutsch in einer tuerkischen Antwort."""
    text = _lies(_antwort("bakim plani", "ancak ekran paylasimi var"))
    assert text.startswith("Bakim plani, ancak ekran paylasimi var:")
    assert "Materialien" not in text


def test_spanischer_begriff_bleibt_spanisch():
    text = _lies(_antwort("plan de mantenimiento", "sin embargo describen el examen"))
    assert text.startswith("Plan de mantenimiento, sin embargo describen el examen:")
    assert "Materialien" not in text


def test_eine_dritte_sprache_bleibt_unberuehrt():
    gap = "Les documents ne disent rien sur « examen »"
    text = _lies(_antwort(gap, "cependant ils décrivent la prestation"))
    assert text.startswith(
        "Les documents ne disent rien sur « examen », cependant ils décrivent")


def test_bindewort_der_anderen_sprache_wird_nicht_mehr_getauscht():
    """Der Tausch konnte nur de gegen en, die Ursache steht jetzt in der Anweisung."""
    gap = "In den Materialien steht nichts zu „Klausur“"
    text = _lies(_antwort(gap, "however beschreiben sie die Prüfungsleistung"))
    assert text.startswith(
        "In den Materialien steht nichts zu „Klausur“, however beschreiben")


# -- Das Satzende steht immer da ------------------------------------------------

def test_bruecke_ohne_doppelpunkt_bekommt_einen():
    text = _lies(_antwort("Folien", "jedoch wird die Präsentation übertragen"))
    assert text.splitlines()[0].endswith("übertragen:")


def test_vorhandener_doppelpunkt_bleibt_einfach():
    text = _lies(_antwort("Folien", "jedoch wird die Präsentation übertragen:"))
    assert text.splitlines()[0].endswith("übertragen:")
    assert "::" not in text


def test_absage_ohne_bruecke_endet_mit_punkt():
    roh = '{"no_info_sentence": "Folien", "bridge": null, "items": [], "body": ""}'
    assert _lies(roh).startswith("Folien.\n\n")


# -- chat.py findet die Absage-Zeile nur ueber diesen Text ----------------------

def test_gap_bleibt_teil_der_angezeigten_zeile():
    strom = AntwortStrom()
    text = "".join(strom.feed(z) for z in _antwort("Folien", "jedoch wird übertragen"))
    assert strom.gap
    assert strom.gap in text.splitlines()[0]


def test_komma_am_satzende_wird_nicht_verdoppelt():
    """Das Modell endet manchmal selbst mit Komma, der Zusammenbau setzt auch eins."""
    text = _lies(_antwort("Materyallerde bilgi yok,", "ancak sunlar var"))
    assert ",," not in text
    assert text.startswith("Materyallerde bilgi yok, ancak sunlar var:")
