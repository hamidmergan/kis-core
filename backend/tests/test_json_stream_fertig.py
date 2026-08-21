"""Der Leser meldet, wann nichts mehr kommt, damit der Strom dann endet.

Gemessen an "wo folien": die Antwort stand nach 13 Sekunden, der Strom lief noch
157 Sekunden weiter und endete erst an der Token-Obergrenze (8192 Token,
172012 ms). Zwei Formen kamen vor. Entweder war das Schema voll und das Modell
schrieb einfach weiter, oder es blieb zwischen zwei Feldern in Leerraum haengen
und schrieb "\\n  " ohne Ende, was JSON zwischen Feldern erlaubt. Beides faellt
im Leser weg, also wachsen weder Zeilenpuffer noch Eintragszahl und keine der
vorhandenen Bremsen greift.
"""

from src.features.ai_assistant.routes._json_stream import (
    LEERLAUF_MAX,
    AntwortStrom,
)


def _antwort(body: str = "Schlusstext.") -> str:
    return (
        '{"no_info_sentence": null, "bridge": null, '
        '"items": [{"term": "Begriff", "text": "Satz."}], '
        '"body": "' + body + '"}'
    )


def _fertig_bei(roh: str, **kw) -> int | None:
    strom = AntwortStrom(**kw)
    for i, z in enumerate(roh):
        strom.feed(z)
        if strom.fertig:
            return i
    return None


# -- Das Schema ist voll --------------------------------------------------


def test_fertig_bleibt_aus_solange_das_schema_laeuft():
    strom = AntwortStrom()
    for z in _antwort()[:-3]:
        strom.feed(z)
    assert strom.fertig is False


def test_fertig_meldet_sich_am_ende_des_letzten_feldes():
    roh = _antwort()
    stelle = _fertig_bei(roh)
    assert stelle is not None
    assert roh[stelle:] == '"}'


def test_das_nachgeplapper_nach_dem_schema_meldet_fertig_sofort():
    roh = _antwort() + " " + _antwort() * 20
    stelle = _fertig_bei(roh)
    assert stelle is not None
    assert stelle < len(_antwort())


def test_der_ueberblick_meldet_ebenso_fertig():
    assert _fertig_bei(_antwort(), max_eintraege=None) is not None


def test_leerer_body_meldet_auch_fertig():
    assert _fertig_bei(_antwort("")) is not None


def test_der_grund_nennt_das_volle_schema():
    strom = AntwortStrom()
    for z in _antwort():
        strom.feed(z)
    assert strom.grund == "schema"


# -- Das Modell bleibt in Leerraum haengen --------------------------------


def _haengt_vor_body(leerraum: int) -> str:
    """Genau der gemessene Fall: nach der Liste kommt nur noch Leerraum."""
    return (
        '{"no_info_sentence": null, "bridge": null, '
        '"items": [{"term": "Begriff", "text": "Satz."}]' + "\n  " * leerraum
    )


def test_endloser_leerraum_vor_dem_letzten_feld_beendet_den_strom():
    stelle = _fertig_bei(_haengt_vor_body(2000))
    assert stelle is not None
    assert stelle < len(_haengt_vor_body(2000))


def test_der_grund_nennt_den_leerlauf():
    strom = AntwortStrom()
    for z in _haengt_vor_body(2000):
        strom.feed(z)
    assert strom.grund == "leerlauf"


def test_die_eintraege_vor_dem_leerlauf_bleiben_stehen():
    strom = AntwortStrom()
    text = "".join(strom.feed(z) for z in _haengt_vor_body(2000))
    assert "- **Begriff**: Satz." in text


def test_normaler_einzug_im_json_loest_nichts_aus():
    # Ein huebsch eingerueckter Aufbau ist erlaubt und darf nicht abbrechen.
    huebsch = (
        '{\n  "no_info_sentence": null,\n  "bridge": null,\n'
        '  "items": [\n    {\n      "term": "Begriff",\n'
        '      "text": "Satz."\n    }\n  ],\n  "body": "Schlusstext."\n}'
    )
    strom = AntwortStrom()
    text = "".join(strom.feed(z) for z in huebsch)
    assert strom.grund == "schema"
    assert text.endswith("Schlusstext.")


def test_zeilenumbrueche_im_fliesstext_loesen_nichts_aus():
    # Im laufenden Satz sind Umbrueche Inhalt, kein Leerlauf.
    lang = "\\n".join(["Ein Absatz."] * (LEERLAUF_MAX + 50))
    strom = AntwortStrom()
    text = "".join(strom.feed(z) for z in _antwort(lang))
    assert strom.grund == "schema"
    assert text.count("Ein Absatz.") == LEERLAUF_MAX + 50


# -- Ohne Schema aendert sich nichts --------------------------------------


def test_ohne_json_meldet_der_leser_nie_fertig():
    strom = AntwortStrom()
    text = "".join(strom.feed(z) for z in "Einfach nur Text ohne Klammern.")
    assert text == "Einfach nur Text ohne Klammern."
    assert strom.fertig is False


def test_roher_text_mit_vielen_umbruechen_laeuft_weiter():
    strom = AntwortStrom()
    roh = "Erst Text.\n" + "\n  " * 2000 + "Dann noch mehr."
    text = "".join(strom.feed(z) for z in roh)
    assert strom.fertig is False
    assert text.endswith("Dann noch mehr.")
