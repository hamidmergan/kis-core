"""The admin limits have to take effect without a restart."""

import pytest

from src import limits
from src.services import tool_limits


@pytest.fixture
def gesetzt(monkeypatch):
    """Fakes settings from the database, without a database."""
    werte: dict[str, str] = {}

    def fake_get_setting(key: str, default: str = "") -> str:
        return werte.get(key, default)

    monkeypatch.setattr(tool_limits.db, "get_setting", fake_get_setting)
    return werte


# Per limit: function, key, default, set value and result.
FAELLE = [
    (tool_limits.max_screencast_slides, "screencast_max_slides",
     limits.MAX_SCREENCAST_SLIDES, "120", 120),
    (tool_limits.max_transcription_seconds, "transcription_max_minutes",
     limits.MAX_AUDIO_SEC, "180", 180 * 60),
    (tool_limits.max_upload_bytes, "upload_max_mb",
     limits.MAX_UPLOAD_BYTES, "800", 800 * 1024 * 1024),
    (tool_limits.results_kept_per_user, "results_kept_per_user",
     limits.MAX_RESULT_FILES, "20", 20),
    (tool_limits.max_open_jobs, "tool_max_open_jobs",
     limits.MAX_OPEN_JOBS_PER_TOOL, "12", 12),
]


@pytest.mark.parametrize("fn,key,vorgabe,roh,erwartet", FAELLE)
def test_vorgabe_ohne_eintrag(gesetzt, fn, key, vorgabe, roh, erwartet):
    assert fn() == vorgabe


@pytest.mark.parametrize("fn,key,vorgabe,roh,erwartet", FAELLE)
def test_eintrag_schlaegt_vorgabe(gesetzt, fn, key, vorgabe, roh, erwartet):
    gesetzt[key] = roh
    assert fn() == erwartet


@pytest.mark.parametrize("fn,key,vorgabe,roh,erwartet", FAELLE)
@pytest.mark.parametrize("muell", ["", "viele", "12,5", None])
def test_muell_faellt_auf_die_vorgabe_zurueck(gesetzt, fn, key, vorgabe, roh, erwartet, muell):
    """A broken entry must not disable a tool."""
    gesetzt[key] = muell
    assert fn() == vorgabe


def test_unbegrenzt_nur_wo_es_erlaubt_ist(gesetzt):
    """-1 means unlimited, but only for the two count limits."""
    gesetzt["results_kept_per_user"] = "-1"
    gesetzt["tool_max_open_jobs"] = "-1"
    assert tool_limits.results_kept_per_user() == -1
    assert tool_limits.max_open_jobs() == -1

    # For the other three unlimited would be a trap.
    for key, fn, vorgabe in (
        ("screencast_max_slides", tool_limits.max_screencast_slides, limits.MAX_SCREENCAST_SLIDES),
        ("transcription_max_minutes", tool_limits.max_transcription_seconds, limits.MAX_AUDIO_SEC),
        ("upload_max_mb", tool_limits.max_upload_bytes, limits.MAX_UPLOAD_BYTES),
    ):
        gesetzt[key] = "-1"
        assert fn() == vorgabe


def test_null_und_negatives_ausser_minus_eins_fallen_zurueck(gesetzt):
    gesetzt["results_kept_per_user"] = "0"
    assert tool_limits.results_kept_per_user() == limits.MAX_RESULT_FILES
    gesetzt["results_kept_per_user"] = "-5"
    assert tool_limits.results_kept_per_user() == limits.MAX_RESULT_FILES
