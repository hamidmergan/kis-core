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
