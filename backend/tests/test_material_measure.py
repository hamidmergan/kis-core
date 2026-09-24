"""Prüft das Messen beim Auswählen: dieselbe Zahl wie beim Start, dieselben Absagen."""

import io

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from src.app import create_app
from src.services import sources
from src.services import workspace_sources as ws
from src.services.source_reading import Source

from tests.test_workspace_sources import _Db, _quelle, _raum


def _datei(name: str, inhalt: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(inhalt), filename=name)


# ── Eine hochgeladene Datei ──────────────────────────────────────────────────

async def test_die_messung_zaehlt_wie_der_start():
    inhalt = ("Ein Satz über das Messen.\n\n" * 400).encode()
    gemessen = await sources.measure_upload(_datei("a.txt", inhalt), locale="de",
                                            schluessel="podcast")
    gelesen = await sources.read_uploads([_datei("a.txt", inhalt)], locale="de",
                                         hoechstens=10, schluessel="podcast")
    assert gemessen == len(gelesen[0].text)
    assert gemessen > 0


async def test_ein_fremdes_format_wird_schon_beim_messen_abgelehnt():
    with pytest.raises(HTTPException) as fehler:
        await sources.measure_upload(_datei("a.exe", b"MZ"), locale="de", schluessel="podcast")
    assert fehler.value.status_code == 400


async def test_eine_leere_datei_wird_schon_beim_messen_abgelehnt():
    with pytest.raises(HTTPException) as fehler:
        await sources.measure_upload(_datei("a.txt", b""), locale="de", schluessel="podcast")
    assert fehler.value.status_code == 400


# ── Eine Quelle aus dem Workspace ────────────────────────────────────────────

def _miss(monkeypatch, *, sources_, quelle, text="Ein Satz."):
    monkeypatch.setattr(ws, "db", _Db(workspace=_raum(), sources=sources_))
    monkeypatch.setattr(ws, "_read_one",
                        lambda q: Source(dateiname=q["filename"], fassung="f", text=text,
                                         stuecke=[], seiten=1))
    return ws.measure_one("w1", quelle, user_id=7, locale="de", schluessel="podcast")


def test_eine_workspace_quelle_meldet_ihre_zeichen(monkeypatch):
    assert _miss(monkeypatch, sources_=[_quelle("a", "A.pdf")], quelle="a",
                 text="x" * 1234) == 1234


def test_eine_fremde_quelle_gibt_es_auch_beim_messen_nicht(monkeypatch):
    with pytest.raises(HTTPException) as fehler:
        _miss(monkeypatch, sources_=[_quelle("a", "A.pdf")], quelle="fremd")
    assert fehler.value.status_code == 404


def test_eine_quelle_die_noch_arbeitet_ist_nicht_messbar(monkeypatch):
    with pytest.raises(HTTPException) as fehler:
        _miss(monkeypatch, sources_=[_quelle("a", "A.pdf", status="indexing")], quelle="a")
    assert fehler.value.status_code == 409


def test_wer_nicht_in_den_raum_darf_misst_auch_nichts(monkeypatch):
    monkeypatch.setattr(ws, "db", _Db(workspace=_raum(user_id=9), sources=[_quelle("a", "A.pdf")]))
    with pytest.raises(HTTPException) as fehler:
        ws.measure_one("w1", "a", user_id=7, locale="de", schluessel="podcast")
    assert fehler.value.status_code == 403


# ── Die Pfade der drei Dienste ───────────────────────────────────────────────

@pytest.mark.parametrize("dienst", ["podcast", "praesentation", "summary"])
def test_jeder_dienst_hat_beide_messpfade(dienst):
    pfade = set(create_app().openapi()["paths"])
    assert f"/{dienst}/measure" in pfade
    assert f"/{dienst}/measure/workspace" in pfade
