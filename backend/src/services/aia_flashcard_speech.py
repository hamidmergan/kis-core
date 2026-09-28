"""Speaks the example sentence of a flashcard, provider and voice come from the admin area."""


def configured_voice() -> tuple[int, str] | None:
    """The default voice while it belongs to the starred provider, otherwise that provider's first voice."""
    from src.features.ai_providers.repository.providers import list_providers_with_capability
    from src.services import tts_standard

    setting = tts_standard.default_voice_setting()
    star = tts_standard.star_id()
    # Without a star the default voice counts as it is, even with an empty provider list.
    if setting and star in (None, setting[0]):
        return setting
    return tts_standard.standard_voice(list_providers_with_capability("tts"), star, setting)


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
    from src.services import tts_job_provider

    chosen = configured_voice()
    if not chosen:
        raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))

    # Exactly the text that reaches the provider.
    text = speech_cache.normalize_sentence(sentence)
    if not text:
        raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))

    def _schluessel(pid: int, vid: str) -> str:
        # The model belongs in the fingerprint, otherwise the old sound stays.
        return speech_cache.fingerprint(text, pid, vid, _SPEED, tts_model_for_provider(pid))

    def _aus_vorrat(key: str) -> bytes | None:
        # A broken pool must not prevent the reading aloud.
        try:
            return speech_cache.get(key)
        except Exception as exc:  # noqa: BLE001 - jeder Datenbankfehler ist derselbe Fall
            logger.warning("Aussprache-Vorrat nicht lesbar: {}", exc)
            return None

    # A sentence the chosen voice already spoke needs no provider, even while that provider is down.
    key = _schluessel(*chosen)
    vorrat = _aus_vorrat(key)
    if vorrat:
        return vorrat
    # One sentence is one job, so the admin's fallback may take over the whole sentence.
    wahl = tts_job_provider.pick(chosen[0], [chosen[1]])
    provider_id, voice_id = wahl.provider_id, wahl.voices[0]
    if wahl.fallback:
        key = _schluessel(provider_id, voice_id)
        vorrat = _aus_vorrat(key)
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
