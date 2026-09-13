"""Die Groesse gilt fuer alle Dateien eines Podcasts zusammen."""

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
    """Zehn mal 40 MB bleiben unter der Summe, die Zahl der Dateien zaehlt hier nicht."""
    _grenze(monkeypatch, 500)
    start._pruefe_gesamtgroesse(_Request(10 * 40 * 1024 * 1024), "de")


def test_eine_einzige_zu_grosse_datei_wird_auch_abgelehnt(monkeypatch):
    _grenze(monkeypatch, 500)
    with pytest.raises(HTTPException):
        start._pruefe_gesamtgroesse(_Request(600 * 1024 * 1024), "de")


def test_ohne_angabe_wird_nicht_geraten(monkeypatch):
    """Fehlt die Angabe, bremst weiter die Grenze je Datei beim Einlesen."""
    _grenze(monkeypatch, 500)
    start._pruefe_gesamtgroesse(_Request(None), "de")
