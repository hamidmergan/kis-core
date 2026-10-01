"""Was die Bild-Aufgaben nach dem Umbau 29.09.2026 an den Anbieter schicken."""

import base64
import contextlib
import io

from PIL import Image

from src.tasks import general_tasks as gt


def _png() -> bytes:
    puffer = io.BytesIO()
    Image.new("RGB", (4, 4)).save(puffer, "PNG")
    return puffer.getvalue()


class _Antwort:
    def __init__(self, status, daten=None, headers=None, inhalt=b"", text=""):
        self.status_code, self._daten, self.headers, self.content, self.text = status, daten, headers or {}, inhalt, text

    def json(self):
        return self._daten


class _Client:
    """Answers in turn and records every call."""

    def __init__(self, *antworten):
        self._antworten = list(antworten)
        self.aufrufe = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, **kwargs):
        self.aufrufe.append((url, kwargs))
        return self._antworten.pop(0)


@contextlib.contextmanager
def _herzschlag(job_uuid):
    yield


def _umgebung(monkeypatch, client, meta=None, dateien=None):
    monkeypatch.setattr(gt.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(gt, "save_job_file",
                        lambda user, job, name, daten: (dateien if dateien is not None else {}).update({name: daten}))
    monkeypatch.setattr(gt, "save_result_meta", lambda user, job, daten: (meta if meta is not None else {}).update(daten))
    monkeypatch.setattr(gt, "_resolve_user_id", lambda j: 1)
    monkeypatch.setattr(gt, "delete_file", lambda p: None)
    monkeypatch.setattr(gt, "save_result_and_evict", lambda *a, **k: None)
    monkeypatch.setattr(gt, "save_result_file", lambda *a, **k: "pfad")
    monkeypatch.setattr(gt, "job_heartbeat", _herzschlag)
    monkeypatch.setattr(gt, "get_file", lambda p: _png())
    monkeypatch.setattr(gt, "_image_http_client", lambda *a, **k: ("http://x", "modell", client))


_BILD = {"data": [{"b64_json": base64.b64encode(_png()).decode()}]}


def test_erzeugen_schickt_groesse_und_schritte(monkeypatch):
    client = _Client(_Antwort(200, _BILD))
    _umgebung(monkeypatch, client)
    gt.run_image_generate.run.__func__(None, "job1", "Apfel", "1344x768", None, steps=28)
    body = client.aufrufe[0][1]["json"]
    assert body["size"] == "1344x768" and body["num_inference_steps"] == 28


def test_der_dateiname_kommt_aus_dem_titel(monkeypatch):
    client = _Client(_Antwort(200, _BILD))
    _umgebung(monkeypatch, client)
    namen = []
    monkeypatch.setattr(gt, "save_result_and_evict", lambda user, job, pfad, name: namen.append(name))
    gt.run_image_generate.run.__func__(None, "job1", "Clean editorial illustration. Subject: Apfel", "1024x1024",
                                        None, steps=28, titel="Roter Apfel")
    assert namen == ["image_Roter_Apfel.png"]


def test_lehnt_der_anbieter_die_groesse_ab_versucht_es_kis_kleiner(monkeypatch):
    """GWDG: Height must be between 1 and 1080."""
    client = _Client(_Antwort(422, {"detail": "Height must be between 1 and 1080"}, text="Height must be"),
                     _Antwort(200, _BILD))
    _umgebung(monkeypatch, client)
    gt.run_image_generate.run.__func__(None, "job1", "Apfel", "1920x1088", None, steps=28)
    assert [a[1]["json"]["size"] for a in client.aufrufe] == ["1920x1088", "1904x1072"]


def test_bearbeiten_schickt_die_berechnete_groesse_und_die_schritte(monkeypatch):
    client = _Client(_Antwort(200, headers={"content-type": "image/png"}, inhalt=_png()))
    _umgebung(monkeypatch, client)
    gt.run_image_edit.run.__func__(None, "job1", "ip", "hoch.png", "blau", None, size="576x1024", steps=15)
    formular = client.aufrufe[0][1]["data"]
    assert formular["size"] == "576x1024" and formular["num_inference_steps"] == "15"


def test_verstehen_schickt_die_anweisung_und_eine_laengengrenze(monkeypatch):
    client = _Client(_Antwort(200, {"choices": [{"message": {"content": "Vier Personen."}}]}))
    _umgebung(monkeypatch, client)
    monkeypatch.setattr(gt.db, "get_setting", lambda k, d=None: "SYSTEM")
    gt.run_image_analyze.run.__func__(None, "job1", "ip", "a.png", "", None, anweisung="Write alternative text.")
    body = client.aufrufe[0][1]["json"]
    text = body["messages"][0]["content"][0]["text"]
    # The general prompt asks for detail and the language of the image, both would override the chosen task.
    assert text == "Write alternative text." and "SYSTEM" not in text
    assert body["max_tokens"] > 0


def test_erzeugen_merkt_sich_beschreibung_und_text_fuers_modell(monkeypatch):
    """Nutzerwunsch 29.09.: die Beschreibung soll zum Bild sichtbar und herunterladbar sein, auch im Verlauf."""
    meta: dict = {}
    _umgebung(monkeypatch, _Client(_Antwort(200, _BILD)), meta)
    gt.run_image_generate.run.__func__(None, "job1", "Skizze. Subject: A red apple", "1024x1024", None, steps=28,
                                        titel="Roter Apfel")
    assert meta["beschreibung"] == "Roter Apfel"
    assert meta["modell_prompt"] == "Skizze. Subject: A red apple"
    assert meta["groesse"] == "1024x1024"


def test_bearbeiten_merkt_sich_die_anweisung(monkeypatch):
    meta: dict = {}
    _umgebung(monkeypatch, _Client(_Antwort(200, headers={"content-type": "image/png"}, inhalt=_png())), meta)
    gt.run_image_edit.run.__func__(None, "job1", "ip", "a.png", "Mache es blau", None, size="1024x1024", steps=25)
    assert meta["beschreibung"] == "Mache es blau" and meta["groesse"] == "1024x1024"


def test_erzeugen_merkt_sich_stil_format_und_qualitaet(monkeypatch):
    """Das Bild zeigt unter dem Prompt, womit es gemacht wurde, auch im Verlauf."""
    meta: dict = {}
    _umgebung(monkeypatch, _Client(_Antwort(200, _BILD)), meta)
    gt.run_image_generate.run.__func__(None, "job1", "Apfel", "1344x768", None, steps=28, titel="Apfel",
                                        angaben={"stil": "foto", "format": "16:9", "qualitaet": "hoch"})
    assert meta["stil"] == "foto" and meta["format"] == "16:9" and meta["qualitaet"] == "hoch"
    assert meta["beschreibung"] == "Apfel"


def test_bearbeiten_behaelt_die_vorlage_fuer_vorher_und_nachher(monkeypatch):
    """Nutzerwunsch 30.09.: Vorher und Nachher soll immer zu sehen sein, auch bei älteren Bildern."""
    meta: dict = {}
    dateien: dict = {}
    _umgebung(monkeypatch, _Client(_Antwort(200, headers={"content-type": "image/png"}, inhalt=_png())), meta, dateien)
    gt.run_image_edit.run.__func__(None, "job1", "ip", "a.jpg", "Mache es blau", None, size="1024x1024", steps=25,
                                   angaben={"format": "vorlage", "qualitaet": "standard"})
    assert meta["vorlage"] == "vorlage.jpg" and dateien["vorlage.jpg"] == _png()
    assert meta["format"] == "vorlage" and meta["qualitaet"] == "standard"


def test_ein_aufgefuelltes_panorama_behaelt_seine_vorlage_ohne_rand(monkeypatch):
    puffer = io.BytesIO()
    Image.new("RGB", (2048, 512), "white").save(puffer, "PNG")
    client = _Client(_Antwort(200, headers={"content-type": "image/png"}, inhalt=puffer.getvalue()))
    dateien: dict = {}
    _umgebung(monkeypatch, client, {}, dateien)
    monkeypatch.setattr(gt, "get_file", lambda p: puffer.getvalue())
    gt.run_image_edit.run.__func__(None, "job1", "ip", "panorama.jpg", "Skyline", None, size="2048x512", steps=25,
                                   zuschnitt={"achse": "hoehe", "anteil": 0.4})
    with Image.open(io.BytesIO(dateien["vorlage.png"])) as vorlage:
        assert (vorlage.width, vorlage.height) == (2048, 205)


def test_der_verlauf_bekommt_die_meta_der_bildauftraege():
    from src.routes.jobs._shared import _META_TOOLS
    assert {"image_generate", "image_edit", "image_analyze"} <= _META_TOOLS


def test_eine_beschreibung_behaelt_ihr_bild_und_ihre_verknuepfung(monkeypatch):
    client = _Client(_Antwort(200, {"choices": [{"message": {"content": "Ein Apfel."}}]}))
    meta, dateien = {}, {}
    _umgebung(monkeypatch, client, meta, dateien)
    gt.run_image_analyze.run.__func__(None, "job1", "ip", "a.jpg", "", None, anweisung="Beschreibe.",
                                      angaben={"quelle": "bild1", "titel": "Beschreiben"})
    assert dateien["vorlage.jpg"] == _png()
    assert meta == {"quelle": "bild1", "titel": "Beschreiben", "vorlage": "vorlage.jpg", "dateiname": "a.jpg"}


def test_ein_aufgefuelltes_panorama_wird_auf_seinen_streifen_zugeschnitten(monkeypatch):
    puffer = io.BytesIO()
    Image.new("RGB", (2048, 512), "white").save(puffer, "PNG")
    client = _Client(_Antwort(200, headers={"content-type": "image/png"}, inhalt=puffer.getvalue()))
    _umgebung(monkeypatch, client)
    gespeichert = []
    monkeypatch.setattr(gt, "save_result_file", lambda user, job, ext, daten: gespeichert.append(daten) or "pfad")
    gt.run_image_edit.run.__func__(None, "job1", "ip", "panorama.png", "Skyline", None, size="2048x512", steps=25,
                                   zuschnitt={"achse": "hoehe", "anteil": 0.4})
    with Image.open(io.BytesIO(gespeichert[0])) as ergebnis:
        assert (ergebnis.width, ergebnis.height) == (2048, 205)
