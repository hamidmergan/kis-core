"""LaTeX in the model answer survives the JSON reader."""

from src.features.ai_assistant.routes._json_stream import AntwortStrom


def _lies(roh: str) -> str:
    strom = AntwortStrom()
    return "".join(strom.feed(z) for z in roh)


def _antwort(body: str) -> str:
    return '{"no_info_sentence": null, "bridge": null, "items": [], "body": "' + body + '"}'


def test_latex_befehle_behalten_ihren_rueckstrich():
    text = _lies(_antwort(r"$4a + b = 2 \text{mod} 26$ und $x \rightarrow y$"))
    assert text == r"$4a + b = 2 \text{mod} 26$ und $x \rightarrow y$"


def test_jeder_anfangsbuchstabe_bleibt_erhalten():
    for befehl in (r"\text", r"\times", r"\bmod", r"\beta", r"\frac", r"\forall",
                   r"\rho", r"\alpha", r"\sqrt"):
        assert _lies(_antwort(f"${befehl}$")) == f"${befehl}$"


def test_zeilenumbruch_bleibt_ein_echter_umbruch():
    # Only the n stays a JSON escape, a line break is more common than the command.
    assert _lies(_antwort("Erste Zeile.\\nZweite Zeile.")) == "Erste Zeile.\nZweite Zeile."


def test_anfuehrungszeichen_und_rueckstrich_bleiben_json_zeichen():
    assert _lies(_antwort('Er sagte \\"Hallo\\".')) == 'Er sagte "Hallo".'
    assert _lies(_antwort(r"Ein \\ Rueckstrich")) == r"Ein \ Rueckstrich"
