"""Image size follows the placeholder, the provider gets the style text plus the description."""

import base64

import pytest

from src.features.praesentation import bild


class TestGroesse:
    """The pixels follow the field at 300 dpi, between a floor and a ceiling on the long side."""

    def test_breites_banner_stoesst_an_die_obergrenze(self):
        # 12.81 inch at 300 dpi would be 3843 px, the ceiling holds it at 1920.
        assert bild.bildgroesse(12.81 * 914400, 3.39 * 914400) == "1920x512"

    def test_mittleres_feld_bekommt_genau_300_dpi(self):
        assert bild.bildgroesse(6.04 * 914400, 3.02 * 914400) == "1808x912"

    def test_kleines_feld_bekommt_weniger_als_frueher(self):
        assert bild.bildgroesse(3.36 * 914400, 2.22 * 914400) == "1008x672"

    def test_winziges_feld_faellt_auf_die_untergrenze(self):
        assert bild.bildgroesse(1 * 914400, 1 * 914400) == "768x768"

    def test_hochformat_dreht_die_lange_seite(self):
        b, h = bild.bildgroesse(1000, 1500).split("x")
        assert int(h) > int(b)

    def test_nie_unter_256_auf_der_kurzen_seite(self):
        assert bild.bildgroesse(100 * 914400, 1 * 914400) == "1920x256"


class _Antwort:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class _Client:
    def __init__(self, antworten):
        self.antworten = list(antworten)
        self.gesendet = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json):
        self.gesendet.append(json)
        return self.antworten.pop(0)


@pytest.fixture
def anbieter(monkeypatch):
    halter = {}

    def client(feature, **kw):
        assert feature == "image_gen"
        return "http://bild/v1", "flux.2-dev", halter["client"]

    monkeypatch.setattr(bild, "_image_http_client", client)
    return halter


def test_liefert_die_bytes_aus_b64(anbieter):
    anbieter["client"] = _Client([_Antwort(200, {"data": [{"b64_json": base64.b64encode(b"png").decode()}]})])
    assert bild.erzeuge("a lab", "1536x400") == b"png"
    assert anbieter["client"].gesendet[0]["size"] == "1536x400"


def test_faellt_bei_abgelehnter_groesse_auf_quadrat(anbieter):
    anbieter["client"] = _Client([_Antwort(400, {"error": "size"}),
                                  _Antwort(200, {"data": [{"b64_json": base64.b64encode(b"q").decode()}]})])
    assert bild.erzeuge("a lab", "1536x400") == b"q"
    assert [g["size"] for g in anbieter["client"].gesendet] == ["1536x400", "1024x1024"]


def test_anderer_fehler_wird_gemeldet(anbieter):
    anbieter["client"] = _Client([_Antwort(500, {"error": "kaputt"})])
    with pytest.raises(RuntimeError):
        bild.erzeuge("a lab", "1024x1024")


def test_prompt_haengt_beschreibung_an_den_stil():
    assert bild.prompt_fuer("Red ink style.", "a lab bench") == f"Red ink style. Subject: a lab bench {bild.OHNE_SCHRIFT}"


def test_woerter_in_anfuehrungszeichen_fliegen_raus():
    roh = ("A triangle. The vertices are labeled 'Leistung' (Performance), 'Termine', and \"Kosten\". "
           "In the center the word „Qualität“ is placed.")
    sauber = bild.ohne_zitate(roh)
    assert not any(w in sauber for w in ("Leistung", "Termine", "Kosten", "Qualität", "Performance"))
    assert sauber == "A triangle. The vertices are labeled, and. In the center the word is placed."


def test_eine_klammer_ohne_zitat_davor_bleibt():
    assert bild.ohne_zitate("a curve (like a bell) on paper") == "a curve (like a bell) on paper"


def test_apostroph_im_englischen_bleibt():
    assert bild.ohne_zitate("the teacher's desk and the students' chairs") == "the teacher's desk and the students' chairs"
