"""The size limit applies to all files of a podcast together."""

import pytest
from fastapi import HTTPException

from src.routes.podcast import start


class _Request:
    def __init__(self, laenge):
        self.headers = {} if laenge is None else {"content-length": str(laenge)}


def _grenze(monkeypatch, mb: int) -> None:
    monkeypatch.setattr(start, "max_upload_bytes", lambda: mb * 1024 * 1024)


def test_zusammen_zu_viel_wird_abgelehnt(monkeypatch):
    _grenze(monkeypatch, 500)
    with pytest.raises(HTTPException) as fehler:
        start._pruefe_gesamtgroesse(_Request(501 * 1024 * 1024), "de")
    assert fehler.value.status_code == 413
    assert "500" in fehler.value.detail


def test_zehn_kleine_dateien_gehen_durch(monkeypatch):
    """Ten times 40 MB stays under the total, the file count does not matter here."""
    _grenze(monkeypatch, 500)
    start._pruefe_gesamtgroesse(_Request(10 * 40 * 1024 * 1024), "de")


def test_eine_einzige_zu_grosse_datei_wird_auch_abgelehnt(monkeypatch):
    _grenze(monkeypatch, 500)
    with pytest.raises(HTTPException):
        start._pruefe_gesamtgroesse(_Request(600 * 1024 * 1024), "de")


def test_ohne_angabe_wird_nicht_geraten(monkeypatch):
    """Without the setting, the per-file limit at read time still applies."""
    _grenze(monkeypatch, 500)
    start._pruefe_gesamtgroesse(_Request(None), "de")
