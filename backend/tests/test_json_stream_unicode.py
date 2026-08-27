"""A JSON escape becomes a special character again."""

from src.features.ai_assistant.routes._json_stream import AntwortStrom


def _lies(roh: str) -> str:
    strom = AntwortStrom()
    return "".join(strom.feed(z) for z in roh)


def _antwort(body: str, no_info: str = "null", items: str = "[]") -> str:
    return (
        '{"no_info_sentence": ' + no_info + ', "bridge": null, "items": '
        + items + ', "body": "' + body + '"}'
    )


def test_griechischer_buchstabe_wird_zum_zeichen():
    assert _lies(_antwort(r"Die Phi-Funktion ($\u03C6$)")) == "Die Phi-Funktion ($φ$)"


def test_grosse_und_kleine_hex_ziffern_zaehlen_beide():
    assert _lies(_antwort(r"\u00e4 \u00C4 \u2192")) == "ä Ä →"


def test_zeichen_ausserhalb_der_grundebene_bleibt_ein_zeichen():
    assert _lies(_antwort(r"\ud83d\ude00")) == "\U0001f600"


def test_latex_befehl_mit_u_behaelt_seinen_rueckstrich():
    assert _lies(_antwort(r"$\underline{x}$")) == r"$\underline{x}$"


def test_auch_im_eintrag_und_in_der_absage():
    roh = _antwort(
        "Rest",
        no_info=r'"Kein Wort zu \u03C6."',
        items=r'[{"term": "Phi", "text": "\u00fcber Zahlen"}]',
    )
    text = _lies(roh)
    assert "Kein Wort zu φ." in text
    assert "über Zahlen" in text
