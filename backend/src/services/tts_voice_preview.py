"""Der kurze Beispielsatz, mit dem sich eine Stimme vorstellt."""

from src.features.ai_assistant.repository import speech_cache

# Geht in den Fingerabdruck ein, eine Aenderung entwertet den Vorrat.
_SPEED = 1.0

_SATZ = {
    "en": "Hello! This is a preview of the selected voice. I hope you enjoy the sound.",
    "de": "Hallo! Dies ist eine Vorschau der ausgewählten Stimme. Ich hoffe, sie gefällt Ihnen.",
}


def preview_text(lang: str) -> str:
    """Der Vorschau-Satz in dieser Sprache, sonst der deutsche."""
    return _SATZ.get(lang, _SATZ["de"])


def preview_audio(provider_id: int, voice_id: str, locale: str = "de") -> bytes:
    """Die Stimme einmal sprechen lassen und die MP3-Bytes zurueckgeben."""
    from fastapi import HTTPException
    from loguru import logger

    from src.dependencies import (
        _voice_language_for,
        get_tts_client_for_provider,
        tts_model_for_provider,
    )
    from src.i18n import t

    # Die Sprache kommt aus der Datenbank, damit der Browser den Schluessel nicht bestimmt.
    lang = _voice_language_for(provider_id, voice_id) if voice_id else locale
    text = preview_text(lang)
    key = speech_cache.fingerprint(
        text, provider_id, voice_id, _SPEED, tts_model_for_provider(provider_id))

    # Vor dem Anbieter gefragt, damit ein Treffer keinen einzigen Netzweg kostet.
    try:
        vorrat = speech_cache.get(key)
    except Exception as exc:  # noqa: BLE001 - jeder Datenbankfehler ist derselbe Fall
        logger.warning("Stimmen-Vorrat nicht lesbar: {}", exc)
        vorrat = None
    if vorrat:
        return vorrat

    try:
        client = get_tts_client_for_provider(provider_id)
    except RuntimeError:
        raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))
    if client is None or not client.is_available():
        raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))

    audio = client.synthesize_chunk(text, voice_id=voice_id, speed=_SPEED)
    try:
        speech_cache.put(key, audio)
    except Exception as exc:  # noqa: BLE001 - der Ton ist da, das Ablegen ist Kuer
        logger.warning("Stimmen-Vorrat nicht beschreibbar: {}", exc)
    return audio
