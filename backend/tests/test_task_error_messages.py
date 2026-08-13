"""Fehlertexte der Werkzeuge sind fuer Leute ohne Technikwissen gedacht.

Wenn der Dienst dahinter ueberlastet ist oder gar nicht antwortet, stand bisher
die rohe Meldung des Anbieters im Bildschirm, etwa
``TTS API error (500): Internal Server Error``. Damit kann niemand etwas
anfangen, und zu tun ist ohnehin nur eines, spaeter noch einmal versuchen.
"""
import pytest

from src.tasks import _errors


class FakeDb:
    """Merkt sich, was als Fehlertext am Job landen wuerde."""

    def __init__(self, locale="de"):
        self.locale = locale
        self.geschrieben = None

    def get_job(self, job_uuid):
        return {"creator_locale": self.locale}

    def update_job_status(self, job_uuid, status, error_message=None):
        self.geschrieben = (status, error_message)


@pytest.fixture
def db(monkeypatch):
    fake = FakeDb()
    monkeypatch.setattr(_errors, "db", fake)
    return fake


# ── Erkennung ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("meldung", [
    "TTS API error (500): Internal Server Error",
    "Server error '502 Bad Gateway' for url 'https://x/v1/audio/speech'",
    "503 Service Unavailable",
    "504 Gateway Timeout",
    "Client error '429 Too Many Requests' for url 'https://x'",
    "The read operation timed out",
    "connection timeout",
])
def test_dienst_ueberlastet_wird_erkannt(meldung):
    assert _errors.is_upstream_busy(Exception(meldung)) is True


@pytest.mark.parametrize("meldung", [
    "400 Bad Request",
    "401 Unauthorized",
    "Voice 'xyz' is not available",
    "Datei ist beschaedigt",
])
def test_eigene_fehler_bleiben_unberuehrt(meldung):
    assert _errors.is_upstream_busy(Exception(meldung)) is False


# ── Text am Job ──────────────────────────────────────────────────────────────

def test_ueberlastung_wird_zu_klartext(db):
    _errors.handle_task_exception(
        "job-1", RuntimeError("TTS API error (500): Internal Server Error"),
        task_label="TTS",
    )
    status, text = db.geschrieben
    assert status == "failed"
    assert "500" not in text
    assert "Internal Server Error" not in text
    assert "überlastet" in text


def test_ueberlastung_auf_englisch(db):
    db.locale = "en"
    _errors.handle_task_exception(
        "job-1", RuntimeError("TTS API error (500): Internal Server Error"),
        task_label="TTS",
    )
    _, text = db.geschrieben
    assert "500" not in text
    assert "try again" in text


def test_andere_fehler_kommen_weiter_wie_bisher(db):
    _errors.handle_task_exception(
        "job-1", ValueError("Datei ist beschaedigt"), task_label="Translate",
    )
    _, text = db.geschrieben
    assert text == "Datei ist beschaedigt"
