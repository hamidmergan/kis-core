"""Der Beispielsatz einer Lernkarte, gesprochen.

Zwei Einstellungen entscheiden, wer spricht: der Anbieter und die Stimme. Beide
sind leer, bis die Verwaltung sie setzt, und solange gibt es den Lautsprecher auf
der Karte nicht. Eine fest eingebaute Anbieternummer wäre bei der nächsten
Hochschule falsch, dort legt die Verwaltung ihre Anbieter selbst an.

Das MODELL steht bewusst nicht hier. Es kommt wie bei jeder anderen Vertonung aus
der Route "Text in Sprache" im Admin-Bereich.
"""

from src import database as db

_PROVIDER_KEY = "aia_flashcard_voice_provider_id"
_VOICE_KEY = "aia_flashcard_voice_id"


def configured_voice() -> tuple[int, str] | None:
    """(Anbieternummer, Stimme) oder None, wenn eines von beiden fehlt.

    Die Anbieternummer steht als Zeichenkette in den Einstellungen, weil die leere
    Wahl "noch nicht eingerichtet" bedeutet und eine Zahl das nicht ausdrücken
    kann. Steht dort etwas, das keine Zahl ist, gilt das als nicht eingerichtet:
    ein fehlender Knopf ist die bessere Antwort auf eine kaputte Einstellung als
    ein Absturz. Eine Anbieternummer kleiner als 1 (0, negativ) ist ebenfalls
    ungültig: die providers.id-Spalte ist ein SERIAL PRIMARY KEY und beginnt bei 1,
    also kann es solche Nummern nicht geben. Der Lesweg verlässt sich bewusst nicht
    darauf, dass jeder Schreibweg vorher geprüft hat: er trifft auch Altdaten,
    künftige zweite Schreibwege oder manuelle Eingriffe in die Datenbank an.
    """
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


def speech_enabled() -> bool:
    """Ob die Ansicht den Lautsprecher zeigen soll."""
    return configured_voice() is not None


# Tempo der Aussprache. Konstante und keine Einstellung: wer langsamer hoeren will,
# ist mit einer anderen Stimme besser bedient als mit einem gedehnten Ton. Sie geht in
# den Fingerabdruck des Vorrats ein, eine Aenderung entwertet ihn also.
_SPEED = 1.0


def synthesize_sentence(sentence: str, locale: str = "de") -> bytes:
    """Einen Satz sprechen und die MP3-Bytes zurückgeben.

    Zuerst wird im Vorrat nachgesehen. Ein Satz kostet beim Anbieter vier bis fünf
    Sekunden, und ohne Vorrat zahlt jede Person im Kurs diesen Preis erneut. Was
    einmal gesprochen wurde, liegt danach für alle bereit, siehe
    ``repository.speech_cache``.

    Zwei Versuche, nicht mehr. Bei der Messung am 2026-08-12 hat myLab eine von
    neun Anfragen mit 500 abgewiesen und beim zweiten Versuch sauber geliefert;
    dafür soll niemand einen Fehler sehen. Ein dritter Versuch würde den
    Lernenden nur länger vor einem Kringel sitzen lassen.

    Bewusst OHNE ``is_available()``: die Erreichbarkeitsprüfung ist selbst eine
    Netzwerkanfrage und würde die Wartezeit fast verdoppeln. Ist der Anbieter
    weg, merkt das der erste Versuch früh genug.
    """
    from fastapi import HTTPException
    from loguru import logger

    from src.dependencies import get_tts_client_for_provider, tts_model_for_provider
    from src.features.ai_assistant.repository import speech_cache
    from src.i18n import t

    chosen = configured_voice()
    if not chosen:
        raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))
    provider_id, voice_id = chosen

    # Genau der Text, der auch beim Anbieter ankommt. Wird hier anders normalisiert
    # als dort, greift der Vorrat nie.
    text = speech_cache.normalize_sentence(sentence)
    if not text:
        raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))
    # Das Modell steht in der Route "Text in Sprache", nicht am Anbieter. Es gehoert in
    # den Fingerabdruck, sonst bedient der Vorrat nach einem Modellwechsel weiter den
    # alten Klang. Der Aufruf liest nur die Datenbank, kein Netz.
    key = speech_cache.fingerprint(
        text, provider_id, voice_id, _SPEED, tts_model_for_provider(provider_id))

    # Ein kaputter Vorrat darf das Vorlesen nicht verhindern, er ist eine Abkürzung
    # und keine Voraussetzung. Faellt er aus, wird eben gesprochen.
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
