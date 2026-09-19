"""Die Fensterpruefung entscheidet vor dem ersten Aufruf, ob eine Datei am Stueck geht."""

from src.features.summary.window import WindowVerdict, tokens_needed, verdict_for
from src.limits import SUMMARY_WINDOW_PROMPT_TOKENS
from src.services.model_limits import ModelProfile


def _profil(fenster: int, quelle: str = "gemessen") -> ModelProfile:
    return ModelProfile(window_tokens=fenster, source=quelle, thinks=False, think_off="")


def test_die_rechnung_zaehlt_datei_antwort_und_aufschlag():
    assert tokens_needed(300_000, 4_000) == 100_000 + 4_000 + SUMMARY_WINDOW_PROMPT_TOKENS


def test_grosses_fenster_nimmt_die_ganze_datei():
    urteil = verdict_for(300_000, 4_000, _profil(262_144))
    assert urteil.fits
    assert urteil.measured


def test_kleines_fenster_lehnt_vorab_ab():
    urteil = verdict_for(300_000, 4_000, _profil(20_080, "gelernt"))
    assert not urteil.fits
    assert urteil.measured
    assert urteil.window_tokens == 20_080
    assert urteil.needed_tokens > 100_000


def test_unvermessenes_fenster_laesst_laufen():
    """Ohne Messung wird nicht geraten, der Auftrag laeuft los und lernt aus der Absage."""
    assert verdict_for(300_000, 4_000, None) == WindowVerdict(True, False, 105_500, 0)
    ohne_zahl = _profil(0, "unbekannt")
    assert verdict_for(300_000, 4_000, ohne_zahl).fits


def test_kleine_datei_passt_auch_in_ein_kleines_fenster():
    assert verdict_for(20_000, 4_000, _profil(20_080, "gelernt")).fits
