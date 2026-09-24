"""Ein Workspace-Dokument darf höchstens so viele Zeichen haben, wie der Adminbereich erlaubt."""

import pytest

from src.features.ai_assistant.tasks.ingestion import SourceTooLong, _zahl, check_length
from src.limits import AIA_SOURCE_MAX_CHARS
from src.services import tool_numbers as tn


@pytest.fixture
def eingestellt(monkeypatch):
    """Der Adminbereich als Wörterbuch, leer heißt nichts eingestellt."""
    werte: dict[str, str] = {}
    monkeypatch.setattr("src.database.get_setting",
                        lambda key, default="": werte.get(key, default))
    return werte


def _stuecke(*laengen: int) -> list[dict]:
    return [{"content": "x" * n, "page_number": i + 1} for i, n in enumerate(laengen)]


def test_ohne_eintrag_gilt_die_grenze_aus_limits(eingestellt):
    assert tn.value_of("aia_source_max_chars") == AIA_SOURCE_MAX_CHARS


def test_genau_an_der_grenze_geht_durch(eingestellt):
    eingestellt["aia_source_max_chars"] = "30000"
    check_length(_stuecke(20_000, 10_000))


def test_ein_zeichen_darueber_wird_abgelehnt(eingestellt):
    eingestellt["aia_source_max_chars"] = "30000"
    with pytest.raises(SourceTooLong) as fehler:
        check_length(_stuecke(20_000, 10_001))
    assert fehler.value.chars == 30_001
    assert fehler.value.limit == 30_000


def test_die_zahl_steht_im_admin_bereich_des_assistenten():
    zahl = tn.BY_KEY["aia_source_max_chars"]
    assert zahl.tool == "aia"
    assert zahl.permission == "settings.assistent.sources"


def test_die_alte_zahl_der_zusammenfassung_ist_weg():
    assert "summary_max_chars_per_source" not in tn.BY_KEY


def test_die_meldung_schreibt_zahlen_wie_die_sprache():
    assert _zahl(500_000, "de") == "500.000"
    assert _zahl(500_000, "en") == "500,000"
