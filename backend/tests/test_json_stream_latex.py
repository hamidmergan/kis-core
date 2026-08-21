"""LaTeX in der Modellantwort ueberlebt den JSON-Leser des Chat-Streams.

Die Antwort kommt als JSON, aber die Modelle maskieren den Rueckstrich darin nicht.
Der Leser hielt "\\t" darum fuer einen Tabulator und machte aus "\\text{mod}" ein
"ext{mod}", das KaTeX als "extmod" anzeigte. Dasselbe traf jeden anderen Befehl,
weil ein unbekannter Buchstabe seinen Rueckstrich verlor.
"""

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
    # Nur das n bleibt ein JSON-Zeichen, weil der Umbruch jede Antwort gliedert und ein
    # Befehl mit n ("\\neq") viel seltener ist als eine neue Zeile.
    assert _lies(_antwort("Erste Zeile.\\nZweite Zeile.")) == "Erste Zeile.\nZweite Zeile."


def test_anfuehrungszeichen_und_rueckstrich_bleiben_json_zeichen():
    assert _lies(_antwort('Er sagte \\"Hallo\\".')) == 'Er sagte "Hallo".'
    assert _lies(_antwort(r"Ein \\ Rueckstrich")) == r"Ein \ Rueckstrich"
