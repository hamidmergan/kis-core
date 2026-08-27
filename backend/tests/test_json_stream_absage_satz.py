"""The sentence about what is missing goes out as the model wrote it."""

from src.features.ai_assistant.routes._json_stream import AntwortStrom


def _lies(roh: str, **kw) -> str:
    strom = AntwortStrom(**kw)
    return "".join(strom.feed(z) for z in roh)


def _antwort(gap: str, bridge: str, items: str = '{"term": "T", "text": "S."}') -> str:
    return (
        '{"no_info_sentence": "' + gap + '", "bridge": "' + bridge + '", '
        '"items": [' + items + '], "body": ""}'
    )


# -- The model's text stays the model's text ------------------------------------

def test_ganzer_satz_bleibt_wie_er_ist():
    gap = "Die Unterlagen nennen keine „Folien“."
    text = _lies(_antwort(gap, "jedoch wird die Präsentation übertragen"))
    assert text.startswith("Die Unterlagen nennen keine „Folien“, jedoch wird")


def test_nackter_begriff_bekommt_keinen_deutschen_rahmen():
    """The code used to build a German sentence around this."""
    text = _lies(_antwort("Folien", "jedoch wird die Präsentation übertragen"))
    assert text.startswith("Folien, jedoch wird die Präsentation übertragen:")
    assert "In den Materialien steht nichts" not in text


def test_tuerkischer_begriff_bleibt_tuerkisch():
    """Exactly this case used to put German into a Turkish answer."""
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
    """The swap could only do de for en, the cause now sits in the instruction."""
    gap = "In den Materialien steht nichts zu „Klausur“"
    text = _lies(_antwort(gap, "however beschreiben sie die Prüfungsleistung"))
    assert text.startswith(
        "In den Materialien steht nichts zu „Klausur“, however beschreiben")


# -- The sentence end is always there -------------------------------------------

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


# -- chat.py finds the refusal line only via this text --------------------------

def test_gap_bleibt_teil_der_angezeigten_zeile():
    strom = AntwortStrom()
    text = "".join(strom.feed(z) for z in _antwort("Folien", "jedoch wird übertragen"))
    assert strom.gap
    assert strom.gap in text.splitlines()[0]


def test_komma_am_satzende_wird_nicht_verdoppelt():
    """The model sometimes ends with a comma itself, and the join adds one too."""
    text = _lies(_antwort("Materyallerde bilgi yok,", "ancak sunlar var"))
    assert ",," not in text
    assert text.startswith("Materyallerde bilgi yok, ancak sunlar var:")
