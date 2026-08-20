"""Der Absage-Satz bleibt ein ganzer Satz, auch wenn das Modell nur den Begriff nennt.

Auf "wo folien" lieferte das Modell gap="Folien" statt eines Satzes, und die
Bruecke endete ohne Doppelpunkt. Angezeigt wurde "Folien, jedoch wird die
Praesentation uebertragen", also ein Satz ohne Anfang und ohne Ende.
"""

from src.features.ai_assistant.routes._json_stream import AntwortStrom


def _lies(roh: str, **kw) -> str:
    strom = AntwortStrom(**kw)
    return "".join(strom.feed(z) for z in roh)


def _antwort(gap: str, bridge: str, items: str = '{"term": "T", "text": "S."}') -> str:
    return (
        '{"gap": "' + gap + '", "bridge": "' + bridge + '", '
        '"items": [' + items + '], "body": ""}'
    )


# -- Der nackte Begriff bekommt einen Satz --------------------------------------

def test_nackter_begriff_wird_zum_satz():
    text = _lies(_antwort("Folien", "jedoch wird die Präsentation übertragen"))
    assert text.startswith("In den Quellen steht nichts zu „Folien“, jedoch wird")


def test_ganzer_satz_bleibt_wie_er_ist():
    gap = "Die Unterlagen nennen keine „Folien“."
    text = _lies(_antwort(gap, "jedoch wird die Präsentation übertragen"))
    assert text.startswith("Die Unterlagen nennen keine „Folien“, jedoch wird")


def test_begriff_mit_eigenen_anfuehrungszeichen_wird_nicht_doppelt_gerahmt():
    text = _lies(_antwort("„Folien“", "jedoch wird die Präsentation übertragen"))
    assert text.startswith("In den Quellen steht nichts zu „Folien“, jedoch")


def test_kurze_wortgruppe_zaehlt_auch_als_begriff():
    text = _lies(_antwort("der genaue Klausurtermin", "jedoch steht ein Zeitraum dabei"))
    assert text.startswith("In den Quellen steht nichts zu „der genaue Klausurtermin“,")


# -- Die Sprache haengt an der Bruecke, nicht an der Oberflaeche -----------------

def test_englische_bruecke_bringt_den_englischen_rahmen():
    text = _lies(_antwort("slides", "however the screen is shared"), sprache="de")
    assert text.startswith('The sources say nothing about "slides", however')


def test_ohne_erkennbare_bruecke_entscheidet_die_oberflaeche():
    text = _lies(_antwort("slides", "instead a screen is shared"), sprache="en")
    assert text.startswith('The sources say nothing about "slides", instead')


# -- Das Satzende steht immer da ------------------------------------------------

def test_bruecke_ohne_doppelpunkt_bekommt_einen():
    text = _lies(_antwort("Folien", "jedoch wird die Präsentation übertragen"))
    assert text.splitlines()[0].endswith("übertragen:")


def test_vorhandener_doppelpunkt_bleibt_einfach():
    text = _lies(_antwort("Folien", "jedoch wird die Präsentation übertragen:"))
    assert text.splitlines()[0].endswith("übertragen:")
    assert "::" not in text


def test_absage_ohne_bruecke_endet_mit_punkt():
    roh = '{"gap": "Folien", "bridge": null, "items": [], "body": ""}'
    assert _lies(roh).startswith("In den Quellen steht nichts zu „Folien“.\n\n")


# -- chat.py findet die Absage-Zeile nur ueber diesen Text ----------------------

def test_gap_bleibt_teil_der_angezeigten_zeile():
    strom = AntwortStrom()
    text = "".join(strom.feed(z) for z in _antwort("Folien", "jedoch wird übertragen"))
    assert strom.gap
    assert strom.gap in text.splitlines()[0]
