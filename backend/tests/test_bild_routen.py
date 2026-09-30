"""Die Routen des Bild-Werkzeugs nach dem Umbau 29.09.2026: Varianten, Format, Größe, Qualität, Stil, Aufgaben."""

import io

import pytest
from fastapi import HTTPException
from PIL import Image
from starlette.datastructures import UploadFile

from src.features.bild import optionen as o
from src.routes import image


class _Aufgabe:
    def __init__(self):
        self.aufrufe = []

    def delay(self, *args, **kwargs):
        self.aufrufe.append((args, kwargs))
        return type("T", (), {"id": f"t{len(self.aufrufe)}"})()


@pytest.fixture
def welt(monkeypatch):
    stand = {"jobs": [], "eingaben": []}
    monkeypatch.setattr(image, "enforce_open_jobs", lambda *a, **k: None)
    monkeypatch.setattr(image, "enforce_tool_burst", lambda *a, **k: None)
    monkeypatch.setattr(image, "enforce_quota", lambda *a, **k: None)
    monkeypatch.setattr(image, "validate_or_raise", lambda *a, **k: None)
    monkeypatch.setattr(image, "create_counted_job", lambda uuid, *a, **k: stand["jobs"].append(uuid))
    monkeypatch.setattr(image, "save_queue_file",
                        lambda user, uuid, ext, inhalt: stand["eingaben"].append(uuid) or f"queue/{uuid}{ext}")
    monkeypatch.setattr(image.db, "set_job_input_path", lambda *a: None)
    monkeypatch.setattr(image.db, "set_job_celery_task_id", lambda *a: None)
    from src.tasks import general_tasks
    for name in ("run_image_generate", "run_image_edit", "run_image_analyze"):
        stand[name] = _Aufgabe()
        monkeypatch.setattr(general_tasks, name, stand[name])
    return stand


NUTZER = {"user_id": 7, "role": "staff"}


def _erzeuge(**felder):
    werte = {"prompt": "Ein Apfel", "format_": "1:1", "groesse": "mittel", "qualitaet": "standard",
             "stil": "keiner", "varianten": 1, "ohne_schrift": True, "prompt_modell": "", "provider_id": None,
             "current_user": NUTZER, "locale": "de"}
    werte.update(felder)
    return image.generate_image(**werte)


def test_jede_variante_ist_ein_eigener_auftrag(welt):
    antwort = _erzeuge(varianten=4)
    assert len(welt["jobs"]) == 4 and antwort["job_uuids"] == welt["jobs"]
    assert antwort["job_uuid"] == welt["jobs"][0]
    assert len(welt["run_image_generate"].aufrufe) == 4


def test_format_groesse_qualitaet_und_stil_kommen_beim_modell_an(welt):
    _erzeuge(format_="16:9", groesse="gross", qualitaet="hoch", stil="skizze", ohne_schrift=False)
    args, kwargs = welt["run_image_generate"].aufrufe[0]
    assert args[1] == o.bild_prompt("Ein Apfel", "skizze", ohne_schrift=False)
    assert args[2] == "1920x1088"
    assert kwargs["steps"] == o.schritte("hoch")
    assert kwargs["titel"] == "Ein Apfel", "der Dateiname folgt der eigenen Beschreibung, nicht dem Stiltext"


def test_eine_ausformulierte_beschreibung_geht_statt_der_kurzen_ans_modell(welt):
    _erzeuge(prompt="Apfel", prompt_modell="A shiny red apple on a wooden table")
    args, _ = welt["run_image_generate"].aufrufe[0]
    assert args[1].startswith("A shiny red apple on a wooden table")


@pytest.mark.parametrize("feld", [{"format_": "2:1"}, {"groesse": "riesig"}, {"qualitaet": "ultra"},
                                  {"stil": "kubismus"}, {"varianten": 0}, {"varianten": 5}])
def test_unbekannte_werte_werden_abgewiesen(welt, feld):
    with pytest.raises(HTTPException) as fehler:
        _erzeuge(**feld)
    assert fehler.value.status_code == 400
    assert welt["jobs"] == []


def _bild(breite, hoehe) -> UploadFile:
    puffer = io.BytesIO()
    Image.new("RGB", (breite, hoehe), "white").save(puffer, format="PNG")
    puffer.seek(0)
    return UploadFile(file=puffer, filename="vorlage.png")


async def test_bearbeiten_haelt_das_seitenverhaeltnis_der_vorlage(welt):
    await image.edit_image(image=_bild(900, 1600), prompt="blau", format_="vorlage", groesse="mittel",
                           qualitaet="standard", varianten=1, provider_id=None, current_user=NUTZER, locale="de")
    _, kwargs = welt["run_image_edit"].aufrufe[0]
    assert kwargs["size"] == o.wie_vorlage(900, 1600, "mittel")
    assert kwargs["steps"] == o.schritte("standard", bearbeiten=True)


def test_erzeugen_gibt_stil_format_und_qualitaet_an_den_auftrag(welt):
    _erzeuge(stil="foto", format_="16:9", qualitaet="hoch")
    _, kwargs = welt["run_image_generate"].aufrufe[0]
    assert kwargs["angaben"] == {"stil": "foto", "format": "16:9", "qualitaet": "hoch"}


async def test_bearbeiten_gibt_format_und_qualitaet_an_den_auftrag(welt):
    await image.edit_image(image=_bild(800, 800), prompt="blau", format_="vorlage", groesse="mittel",
                           qualitaet="entwurf", varianten=1, provider_id=None, current_user=NUTZER, locale="de")
    _, kwargs = welt["run_image_edit"].aufrufe[0]
    assert kwargs["angaben"] == {"format": "vorlage", "qualitaet": "entwurf"}


@pytest.fixture
def vorlage_welt(monkeypatch):
    jobs = {"eigen": {"user_id": 7, "tool": "image_edit"}, "fremd": {"user_id": 8, "tool": "image_edit"},
            "erzeugt": {"user_id": 7, "tool": "image_generate"}}
    monkeypatch.setattr(image.db, "get_job", lambda uuid: jobs.get(uuid))
    monkeypatch.setattr(image, "load_result_meta", lambda user, uuid: {"vorlage": "vorlage.png"})
    monkeypatch.setattr(image, "get_job_file", lambda user, uuid, name: b"vorher")


def test_die_vorlage_bekommt_nur_wer_das_bild_bearbeitet_hat(vorlage_welt):
    antwort = image.edit_source("eigen", current_user=NUTZER, locale="de")
    assert antwort.body == b"vorher" and antwort.media_type == "image/png"
    for fremd in ("fremd", "erzeugt", "unbekannt"):
        with pytest.raises(HTTPException) as fehler:
            image.edit_source(fremd, current_user=NUTZER, locale="de")
        assert fehler.value.status_code == 404


def test_ein_altes_bearbeitetes_bild_ohne_vorlage_meldet_404(vorlage_welt, monkeypatch):
    monkeypatch.setattr(image, "load_result_meta", lambda user, uuid: {"beschreibung": "blau"})
    with pytest.raises(HTTPException) as fehler:
        image.edit_source("eigen", current_user=NUTZER, locale="de")
    assert fehler.value.status_code == 404


async def test_zwei_varianten_beim_bearbeiten_haben_je_eine_eigene_vorlage(welt):
    """Jeder Auftrag löscht seine Vorlage am Ende, eine geteilte wäre für den zweiten weg."""
    antwort = await image.edit_image(image=_bild(800, 800), prompt="blau", format_="16:9", groesse="klein",
                                     qualitaet="entwurf", varianten=2, provider_id=None, current_user=NUTZER,
                                     locale="de")
    assert len(antwort["job_uuids"]) == 2 and welt["eingaben"] == welt["jobs"]
    assert welt["run_image_edit"].aufrufe[1][1]["size"] == "1024x576"


async def test_bearbeiten_mit_mehr_als_zwei_varianten_wird_abgewiesen(welt):
    with pytest.raises(HTTPException):
        await image.edit_image(image=_bild(800, 800), prompt="blau", format_="vorlage", groesse="mittel",
                               qualitaet="standard", varianten=3, provider_id=None, current_user=NUTZER, locale="de")


async def test_verstehen_schickt_die_anweisung_der_aufgabe_in_der_gewaehlten_sprache(welt):
    await image.analyze_image(image=_bild(400, 300), prompt="", aufgabe="text", sprache="en", provider_id=None,
                              current_user=NUTZER, locale="de")
    _, kwargs = welt["run_image_analyze"].aufrufe[0]
    assert kwargs["anweisung"] == o.analyse_anweisung("text", "en", "")


async def test_eine_frage_ohne_aufgabe_bleibt_eine_frage(welt):
    """Ältere Oberflächen schicken nur das Textfeld."""
    await image.analyze_image(image=_bild(400, 300), prompt="Wie viele Personen?", aufgabe="", sprache="",
                              provider_id=None, current_user=NUTZER, locale="de")
    _, kwargs = welt["run_image_analyze"].aufrufe[0]
    assert kwargs["anweisung"] == o.analyse_anweisung("frage", "de", "Wie viele Personen?")


async def test_eine_eigene_frage_ohne_text_wird_abgewiesen(welt):
    with pytest.raises(HTTPException) as fehler:
        await image.analyze_image(image=_bild(400, 300), prompt=" ", aufgabe="frage", sprache="de",
                                  provider_id=None, current_user=NUTZER, locale="de")
    assert fehler.value.status_code == 400


def test_ausformulieren_gibt_die_antwort_des_llm_zurueck(monkeypatch):
    from src.features.bild import beschreibung
    monkeypatch.setattr(image, "enforce_tool_burst", lambda *a, **k: None)
    monkeypatch.setattr(beschreibung, "ausformulieren", lambda text: f"EN: {text}")
    assert image.enhance_prompt(prompt="Apfel", current_user=NUTZER, locale="de") == {"prompt": "EN: Apfel"}


def test_ausformulieren_ohne_text_wird_abgewiesen(monkeypatch):
    monkeypatch.setattr(image, "enforce_tool_burst", lambda *a, **k: None)
    with pytest.raises(HTTPException):
        image.enhance_prompt(prompt="  ", current_user=NUTZER, locale="de")


def test_stoesst_eine_spaetere_variante_an_die_grenze_bleiben_die_gestarteten(welt, monkeypatch):
    """Wer schon offene Aufträge hat, bekommt so viele Varianten wie Platz ist, statt eines Fehlers ohne Bilder."""
    def mit_grenze(uuid, *a, **k):
        if len(welt["jobs"]) >= 2:
            raise HTTPException(status_code=409, detail="zu viele")
        welt["jobs"].append(uuid)
    monkeypatch.setattr(image, "create_counted_job", mit_grenze)
    antwort = _erzeuge(varianten=4)
    assert len(antwort["job_uuids"]) == 2 and antwort["teilweise"] is True


def test_scheitert_schon_die_erste_variante_bleibt_es_ein_fehler(welt, monkeypatch):
    def voll(*a, **k):
        raise HTTPException(status_code=409, detail="zu viele")
    monkeypatch.setattr(image, "create_counted_job", voll)
    with pytest.raises(HTTPException) as fehler:
        _erzeuge(varianten=2)
    assert fehler.value.status_code == 409


async def test_ein_panorama_geht_aufgefuellt_zum_anbieter_und_wird_danach_zugeschnitten(welt, monkeypatch):
    inhalte = []
    monkeypatch.setattr(image, "save_queue_file",
                        lambda user, uuid, ext, inhalt: inhalte.append((ext, inhalt)) or f"queue/{uuid}{ext}")
    await image.edit_image(image=_bild(4000, 400), prompt="Skyline", format_="vorlage", groesse="mittel",
                           qualitaet="standard", varianten=1, provider_id=None, current_user=NUTZER, locale="de")
    ext, inhalt = inhalte[0]
    with Image.open(io.BytesIO(inhalt)) as aufgefuellt:
        assert (aufgefuellt.width, aufgefuellt.height) == (4000, 1000) and ext == ".png"
    _, kwargs = welt["run_image_edit"].aufrufe[0]
    assert kwargs["zuschnitt"] == {"achse": "hoehe", "anteil": 0.4}
    assert kwargs["size"] == o.wie_vorlage(4000, 1000, "mittel")


async def test_mit_festem_format_wird_nicht_zurueckgeschnitten(welt):
    await image.edit_image(image=_bild(4000, 400), prompt="Skyline", format_="16:9", groesse="mittel",
                           qualitaet="standard", varianten=1, provider_id=None, current_user=NUTZER, locale="de")
    _, kwargs = welt["run_image_edit"].aufrufe[0]
    assert kwargs["zuschnitt"] is None
