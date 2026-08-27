"""The limits have to take effect on the routes, not just be readable."""

import pytest

from src.limits import MAX_RESULT_FILES


@pytest.fixture
def gesetzt(monkeypatch):
    """Fakes a setting, without a database."""
    werte: dict[str, str] = {}
    from src.services import tool_limits

    monkeypatch.setattr(
        tool_limits.db, "get_setting",
        lambda key, default="": werte.get(key, default),
    )
    return werte


def test_folienzahl_kommt_aus_der_einstellung(gesetzt):
    from src.services.tool_limits import max_screencast_slides

    gesetzt["screencast_max_slides"] = "3"
    assert max_screencast_slides() == 3


def test_aufbewahrung_raeumt_nach_der_einstellung(gesetzt):
    from src.features.jobs.repository._retention import select_jobs_to_evict

    jobs = [{"job_uuid": str(i), "status": "completed"} for i in range(10)]

    gesetzt["results_kept_per_user"] = "4"
    assert len(select_jobs_to_evict(jobs)) == 6

    gesetzt["results_kept_per_user"] = "9"
    assert len(select_jobs_to_evict(jobs)) == 1


def test_unbegrenzt_raeumt_gar_nichts(gesetzt):
    """-1 has to switch the cleanup off, not cut from the back."""
    from src.features.jobs.repository._retention import select_jobs_to_evict

    jobs = [{"job_uuid": str(i), "status": "completed"} for i in range(10)]
    gesetzt["results_kept_per_user"] = "-1"
    assert select_jobs_to_evict(jobs) == []


def test_ohne_einstellung_gilt_die_vorgabe(gesetzt):
    from src.features.jobs.repository._retention import select_jobs_to_evict

    jobs = [{"job_uuid": str(i), "status": "completed"} for i in range(MAX_RESULT_FILES + 3)]
    assert len(select_jobs_to_evict(jobs)) == 3


def test_laufende_auftraege_werden_nie_geraeumt(gesetzt):
    """Existing behaviour the rework must not break."""
    from src.features.jobs.repository._retention import select_jobs_to_evict

    gesetzt["results_kept_per_user"] = "1"
    jobs = [
        {"job_uuid": "neu", "status": "completed"},
        {"job_uuid": "laeuft", "status": "running"},
        {"job_uuid": "alt", "status": "completed"},
    ]
    assert [j["job_uuid"] for j in select_jobs_to_evict(jobs)] == ["alt"]


def test_dateigroesse_in_bytes(gesetzt):
    from src.services.tool_limits import max_upload_bytes

    gesetzt["upload_max_mb"] = "42"
    assert max_upload_bytes() == 42 * 1024 * 1024


def test_aufnahmelaenge_in_sekunden(gesetzt):
    from src.services.tool_limits import max_transcription_seconds

    gesetzt["transcription_max_minutes"] = "7"
    assert max_transcription_seconds() == 420


def test_zu_lange_aufnahme_meldet_die_eingestellte_grenze(gesetzt):
    """The refusal has to name the CURRENT limit, not the old constant."""
    from src.services.openai_compat_llm._chunking import AudioTooLongError
    from src.services.openai_compat_llm import _whisper_chunked

    gesetzt["transcription_max_minutes"] = "30"
    with pytest.raises(AudioTooLongError) as fehler:
        _whisper_chunked._reject_if_too_long(31 * 60)
    assert fehler.value.max_sec == 30 * 60
    assert "30 min" in str(fehler.value)


def test_erlaubte_laenge_geht_durch(gesetzt):
    from src.services.openai_compat_llm import _whisper_chunked

    gesetzt["transcription_max_minutes"] = "30"
    _whisper_chunked._reject_if_too_long(29 * 60)  # darf nicht werfen
