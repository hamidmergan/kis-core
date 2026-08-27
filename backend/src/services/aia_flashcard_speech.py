"""Speaks the example sentence of a flashcard, provider and voice come from the admin area."""

from src import database as db

_PROVIDER_KEY = "aia_flashcard_voice_provider_id"
_VOICE_KEY = "aia_flashcard_voice_id"


def configured_voice() -> tuple[int, str] | None:
    """Provider and voice, otherwise the first available, or None when there is none."""
    return _ausdruecklich_gewaehlt() or _erste_stimme()


def _ausdruecklich_gewaehlt() -> tuple[int, str] | None:
    """What the settings say, as long as it is usable."""
    raw_provider = (db.get_setting(_PROVIDER_KEY, "") or "").strip()
    voice = (db.get_setting(_VOICE_KEY, "") or "").strip()
    if not raw_provider or not voice:
        return None
    try:
        provider_id = int(raw_provider)
    except ValueError:
        return None
    if provider_id < 1:
        return None
    return provider_id, voice


def _erste_stimme() -> tuple[int, str] | None:
    """The first voice of the first enabled provider that can speak."""
    from src.features.ai_providers.repository.providers import list_providers_with_capability

    for provider in list_providers_with_capability("tts"):
        for voice in (provider.get("voices") or []):
            voice_id = (voice.get("voice_id") or "").strip()
            if voice_id:
                return int(provider["id"]), voice_id
    return None


def speech_enabled() -> bool:
    """Whether the view should show the speaker."""
    return configured_voice() is not None


# Speed of the pronunciation, it goes into the pool fingerprint.
_SPEED = 1.0


def synthesize_sentence(sentence: str, locale: str = "de") -> bytes:
    """Speaks a sentence and returns the MP3 bytes, with pool and two attempts."""
    from fastapi import HTTPException
    from loguru import logger

    from src.dependencies import get_tts_client_for_provider, tts_model_for_provider
    from src.features.ai_assistant.repository import speech_cache
    from src.i18n import t

    chosen = configured_voice()
    if not chosen:
        raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))
    provider_id, voice_id = chosen

    # Exactly the text that reaches the provider.
    text = speech_cache.normalize_sentence(sentence)
    if not text:
        raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))
    # The model belongs in the fingerprint, otherwise the old sound stays.
    key = speech_cache.fingerprint(
        text, provider_id, voice_id, _SPEED, tts_model_for_provider(provider_id))

    # A broken pool must not prevent the reading aloud.
    try:
        vorrat = speech_cache.get(key)
    except Exception as exc:  # noqa: BLE001 - jeder Datenbankfehler ist derselbe Fall
        logger.warning("Aussprache-Vorrat nicht lesbar: {}", exc)
        vorrat = None
    if vorrat:
        return vorrat

    try:
        client = get_tts_client_for_provider(provider_id)
    except RuntimeError as exc:
        logger.warning("Lernkarten-Aussprache: Anbieter {} nicht verfuegbar: {}", provider_id, exc)
        raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))
    if client is None:
        raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))

    for versuch in (1, 2):
        try:
            audio = client.synthesize_chunk(text, voice_id=voice_id, speed=_SPEED)
        except Exception as exc:  # noqa: BLE001 - jeder Anbieterfehler ist derselbe Fall
            logger.warning("Lernkarten-Aussprache Versuch {} fehlgeschlagen: {}", versuch, exc)
            continue
        try:
            speech_cache.put(key, audio)
        except Exception as exc:  # noqa: BLE001 - der Ton ist da, das Ablegen ist Kuer
            logger.warning("Aussprache-Vorrat nicht beschreibbar: {}", exc)
        return audio

    raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))
