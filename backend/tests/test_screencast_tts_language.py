"""The voicing gets the screencast's target language, not a fixed EN."""

import asyncio

import pytest

from src.services.screencast.generation import generate_all_tts


class FakeTts:
    def __init__(self):
        self.sprachen = []

    def synthesize_with_timestamps(self, text, language, *, voice_id, speed):
        self.sprachen.append(language)
        return {"audio_bytes": b"mp3", "alignment": None}


def _lauf(tmp_path, **kwargs):
    tts = FakeTts()
    asyncio.run(generate_all_tts(["Ein Skript."], tts, tmp_path, 1.0, voice_id="alloy", **kwargs))
    return tts.sprachen


def test_zielsprache_wird_durchgereicht(tmp_path):
    assert _lauf(tmp_path, target_lang="FR") == ["FR"]


def test_ohne_zielsprache_bleibt_die_sprache_unbekannt(tmp_path):
    """Unknown means digits stay as they are instead of being spelled out wrongly."""
    assert _lauf(tmp_path) == [""]


@pytest.mark.parametrize("ziel", ["EN-US", "DE", ""])
def test_jede_zielsprache_kommt_unveraendert_an(tmp_path, ziel):
    assert _lauf(tmp_path, target_lang=ziel) == [ziel]
