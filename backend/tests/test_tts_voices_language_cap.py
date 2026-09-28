"""The voice picker offers German, English and language-less voices only."""

import pytest

from src.routes import tts as tts_routes


FAKE_PROVIDERS = [
    {
        "id": 1,
        "name": "Stimmen lokal",
        "voices": [
            {"voice_id": "a", "name": "Anna", "language": "de"},
            {"voice_id": "b", "name": "Ben", "language": "en"},
            {"voice_id": "c", "name": "Claire", "language": "fr"},
            {"voice_id": "d", "name": "Diego", "language": "es"},
            {"voice_id": "e", "name": "Effect", "language": ""},
        ],
    },
]


@pytest.fixture(autouse=True)
def admin(monkeypatch):
    """Star and default voice from the admin area, both unset by default."""
    stand = {"stern": None, "einstellungen": {}}
    monkeypatch.setattr("src.database.get_route", lambda f: {"provider_id": stand["stern"]} if f == "tts" else None)
    monkeypatch.setattr("src.database.get_setting", lambda key, default="": stand["einstellungen"].get(key, default))
    return stand


def _erreichbar(monkeypatch, anbieter):
    async def fake_reachable():
        return anbieter

    monkeypatch.setattr("src.dependencies.get_reachable_tts_providers_with_voices", fake_reachable)


ZWEI = [
    {"id": 21, "name": "THL myLab", "voices": [{"voice_id": "alloy", "name": "Alloy", "language": "en"}]},
    {"id": 89, "name": "Kokoro", "voices": [
        {"voice_id": "ff_siwis", "name": "Siwis", "language": "fr"},
        {"voice_id": "af_heart", "name": "Heart", "language": "en"},
        {"voice_id": "de_anna", "name": "Anna", "language": "de"},
    ]},
]


@pytest.mark.asyncio
async def test_der_sternanbieter_steht_vorn(monkeypatch, admin):
    _erreichbar(monkeypatch, ZWEI)
    admin["stern"] = 89
    antwort = await tts_routes.get_tts_providers_with_voices()
    assert [p["id"] for p in antwort["providers"]] == [89, 21]


@pytest.mark.asyncio
async def test_vorausgewaehlt_ist_die_standardstimme_des_sternanbieters(monkeypatch, admin):
    _erreichbar(monkeypatch, ZWEI)
    admin["stern"] = 89
    admin["einstellungen"] = {"aia_flashcard_voice_provider_id": "89", "aia_flashcard_voice_id": "de_anna"}
    antwort = await tts_routes.get_tts_providers_with_voices()
    assert antwort["default"] == {"provider_id": 89, "voice_id": "de_anna"}


@pytest.mark.asyncio
async def test_eine_ausgefilterte_sprache_wird_nie_vorausgewaehlt(monkeypatch, admin):
    _erreichbar(monkeypatch, ZWEI)
    admin["stern"] = 89
    admin["einstellungen"] = {"aia_flashcard_voice_provider_id": "89", "aia_flashcard_voice_id": "ff_siwis"}
    antwort = await tts_routes.get_tts_providers_with_voices()
    assert antwort["default"] == {"provider_id": 89, "voice_id": "af_heart"}


@pytest.mark.asyncio
async def test_ohne_anbieter_gibt_es_keine_vorauswahl(monkeypatch, admin):
    _erreichbar(monkeypatch, [])
    admin["stern"] = 21
    antwort = await tts_routes.get_tts_providers_with_voices()
    assert antwort == {"providers": [], "default": None}


@pytest.mark.asyncio
async def test_nur_deutsch_englisch_und_sprachlos_kommen_durch(monkeypatch):
    async def fake_reachable():
        return FAKE_PROVIDERS

    monkeypatch.setattr(
        "src.dependencies.get_reachable_tts_providers_with_voices", fake_reachable,
    )

    antwort = await tts_routes.get_tts_providers_with_voices()

    voice_ids = {v["voice_id"] for v in antwort["providers"][0]["voices"]}
    assert voice_ids == {"a", "b", "e"}


@pytest.mark.asyncio
async def test_ein_provider_ohne_passende_stimme_bleibt_mit_leerer_liste(monkeypatch):
    async def fake_reachable():
        return [{"id": 2, "name": "Nur Fremdsprachen", "voices": [
            {"voice_id": "x", "name": "Xavier", "language": "tr"},
        ]}]

    monkeypatch.setattr(
        "src.dependencies.get_reachable_tts_providers_with_voices", fake_reachable,
    )

    antwort = await tts_routes.get_tts_providers_with_voices()

    assert antwort["providers"][0]["voices"] == []
