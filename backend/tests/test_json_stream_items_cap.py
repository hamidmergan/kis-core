"""Die Namensbruecke bleibt kurz, auch wenn das Modell endlos Eintraege liefert.

Auf "wann klausur" lieferte das Modell ueber hundert Eintraege, weil das Feld
"items" nirgends eine Obergrenze hatte. Der Leser gibt nur noch die ersten
Eintraege aus und liest den Rest still zu Ende, damit "body" danach noch stimmt.
"""

from src.features.ai_assistant.routes._json_stream import (
    MAX_EINTRAEGE,
    AntwortStrom,
)


def _lies(roh: str) -> str:
    strom = AntwortStrom()
    return "".join(strom.feed(z) for z in roh)


def _antwort(anzahl: int, body: str = "") -> str:
    eintraege = ", ".join(
        '{"term": "Begriff %d", "text": "Satz %d."}' % (i, i)
        for i in range(1, anzahl + 1)
    )
    return (
        '{"gap": "Klausurtermin", "bridge": "jedoch steht nur dies dabei:", '
        '"items": [' + eintraege + '], "body": "' + body + '"}'
    )


def test_nur_die_ersten_eintraege_erscheinen():
    text = _lies(_antwort(40))
    assert text.count("- **") == MAX_EINTRAEGE


def test_eintrag_ueber_der_grenze_faellt_ganz_weg():
    text = _lies(_antwort(40))
    assert f"Begriff {MAX_EINTRAEGE}" in text
    assert f"Begriff {MAX_EINTRAEGE + 1}" not in text
    assert f"Satz {MAX_EINTRAEGE + 1}." not in text


def test_wenige_eintraege_bleiben_vollstaendig():
    text = _lies(_antwort(2))
    assert "- **Begriff 1**: Satz 1." in text
    assert "- **Begriff 2**: Satz 2." in text


def test_absage_und_bruecke_bleiben_ein_satz():
    assert _lies(_antwort(40)).startswith(
        "In den Quellen steht nichts zu \u201eKlausurtermin\u201c, jedoch steht nur dies dabei:\n"
    )


def test_der_body_kommt_nach_gekappten_eintraegen_noch_an():
    # Der Leser muss die uebersprungenen Eintraege trotzdem sauber zu Ende parsen.
    assert _lies(_antwort(40, "Schlusstext.")).endswith("Schlusstext.")


def test_der_leser_meldet_wenn_es_genug_ist():
    # Ohne dieses Signal schreibt das Modell unsichtbar weiter und die Leitung schweigt.
    strom = AntwortStrom()
    roh = _antwort(40)
    genug_bei = None
    for i, z in enumerate(roh):
        strom.feed(z)
        if strom.genug and genug_bei is None:
            genug_bei = i
    assert genug_bei is not None
    assert genug_bei < len(roh) - 100


def test_genug_bleibt_aus_solange_die_liste_kurz_ist():
    strom = AntwortStrom()
    for z in _antwort(MAX_EINTRAEGE):
        strom.feed(z)
    assert strom.genug is False


def test_der_ueberblick_faehrt_ohne_deckel():
    # Beim Ueberblick ist die Breite die Leistung, darum darf dort nichts wegfallen.
    strom = AntwortStrom(max_eintraege=None)
    text = "".join(strom.feed(z) for z in _antwort(40))
    assert text.count("- **") == 40
    assert strom.genug is False


def test_die_fuenf_stehen_nur_im_prompt_der_einzelfrage():
    # Der Ueberblick-Prompt bleibt Zeichen fuer Zeichen der alte, sonst schrumpft
    # seine Abdeckung.
    from src.features.ai_assistant.prompts.rag_chat.prompts import aia_system_rag
    knapp, breit = aia_system_rag("de"), aia_system_rag("de", overview=True)
    assert "AT MOST FIVE entries." in knapp
    assert "AT MOST FIVE" not in breit
    nur_knapp = [ln for ln in knapp.splitlines() if ln not in breit.splitlines()]
    assert len(nur_knapp) == 1
