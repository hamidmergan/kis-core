"""Text downloads carry the UTF-8 mark, else Safari shows a downloaded file with Ã¼ instead of ü."""

import asyncio

from src.routes.jobs import _download
from src.utils.download_header import UTF8_BOM, utf8_download


def _body(response) -> bytes:
    async def sammeln():
        return b"".join([teil async for teil in response.body_iterator])
    return asyncio.run(sammeln())


def _job(monkeypatch, pfad: str, inhalt: bytes):
    monkeypatch.setattr(_download.db, "get_job", lambda uuid: {
        "user_id": 1, "status": "success", "result_path": pfad, "result_filename": "Übersicht.md",
    })
    monkeypatch.setattr(_download, "get_file", lambda p: inhalt)


def test_text_bekommt_die_kennung_genau_einmal():
    assert utf8_download("gegenüber") == UTF8_BOM + "gegenüber".encode()
    assert utf8_download(UTF8_BOM + "ä".encode()) == UTF8_BOM + "ä".encode()


def test_markdown_ergebnis_kommt_mit_kennung(monkeypatch):
    _job(monkeypatch, "users/1/jobs/j/output.md", "# Übersicht\n".encode())
    antwort = _download.download_job_result("j", {"user_id": 1}, "de")
    daten = _body(antwort)
    assert daten == UTF8_BOM + "# Übersicht\n".encode()
    assert antwort.headers["content-length"] == str(len(daten))


def test_ton_bleibt_unberuehrt(monkeypatch):
    _job(monkeypatch, "users/1/jobs/j/output.mp3", b"ID3ton")
    assert _body(_download.download_job_result("j", {"user_id": 1}, "de")) == b"ID3ton"
