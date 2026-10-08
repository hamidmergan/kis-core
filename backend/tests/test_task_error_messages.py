"""Error texts are meant for people without technical knowledge."""
import pytest

from src.tasks import _errors


class FakeDb:
    """Remembers what would land on the job as an error text."""

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
    # A transient error no longer fails the job, it counts one attempt. Same text either way.
    from src.services import job_recovery

    def anlauf(job_uuid, message, **kwargs):
        fake.geschrieben = ("attempt", message)
        fake.busy = kwargs.get("busy", False)
        return "waiting_retry"

    monkeypatch.setattr(job_recovery, "attempt_failed", anlauf)
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
    # Lauf 14: ein kurzer Aussetzer von myLab beendete ein Podcast-Skript endgültig.
    "Connection error.",
    # Lauf 11: die Namensauflösung fiel unter Last aus, Text in Audio scheiterte.
    "[Errno -3] Temporary failure in name resolution",
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


# ── Text on the job ──────────────────────────────────────────────────────────

def test_ueberlastung_wird_zu_klartext(db):
    _errors.handle_task_exception(
        "job-1", RuntimeError("TTS API error (500): Internal Server Error"),
        task_label="TTS",
    )
    status, text = db.geschrieben
    # Transient: the job resumes by itself instead of failing.
    assert status == "attempt"
    assert "500" not in text
    assert "Internal Server Error" not in text
    assert "Rechenkapazität" in text


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


def test_ein_voller_anbieter_wird_als_voll_weitergereicht(db):
    """Nur so wartet der Auftrag, statt einen seiner drei Anläufe zu verbrauchen."""
    _errors.handle_task_exception("j", RuntimeError("TTS API error (500): Internal Server Error"),
                                  task_label="TTS")
    assert db.busy is True


def test_ein_echter_fehler_ist_nicht_voll(db):
    _errors.handle_task_exception("j", RuntimeError("Datei kaputt"), task_label="TTS")
    assert db.busy is False



def test_ein_zu_kleines_fenster_wird_in_worten_gemeldet():
    from src.services.text_map import WindowTooSmall
    from src.tasks._errors import window_too_small_message

    text = window_too_small_message(WindowTooSmall(16384), "de")
    assert "16.384" in text and "32.768" in text
    assert window_too_small_message(WindowTooSmall(16384), "en").count("16,384") == 1
