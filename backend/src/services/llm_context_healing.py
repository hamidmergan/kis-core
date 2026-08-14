"""Zu viel Kontext: kuerzen und einmal wiederholen, statt den Lauf abzubrechen.

Der Chat kann das seit dem 14.08.2026 direkt in seiner Stream-Schleife. Die Werkzeuge
(Mindmap, Datentabelle, Quiz, Lernkarten, Lueckentext, Grammatik, Glossar) konnten es
nicht, und das fiel nicht auf, solange ein unvermessenes Modell den Vorsichtswert von
32768 Token bekam: bei 58.982 Zeichen laeuft nichts ueber.

Seit die Budgets eine feste Obergrenze haben, ist das anders herum. Ein Modell, dessen
Groesse KIS nicht kennt, bekommt 600.000 Zeichen, also rund 200.000 Token. Von den 16
GWDG-Modellen verraten zwei ihre Groesse nicht, und ``openai-gpt-oss-120b`` hat davon
nur 131.072. Ohne diese Wiederholung braeche dort jeder Werkzeug-Lauf ab, und weil
nichts gelernt wuerde, auch jeder naechste.

Absichtlich genau EIN zweiter Versuch. Die Absage nennt die Fenstergroesse, der zweite
Aufruf passt also sicher. Eine Schleife wuerde nur Ratenkontingent verbrennen.
"""

from __future__ import annotations

from loguru import logger

from src.services import model_limits


def create_with_shrink(client, *, model: str, messages: list[dict], **kwargs):
    """``client.chat.completions.create`` mit Kuerzen und einem zweiten Versuch.

    Lehnt der Anbieter ab und nennt dabei seine Fenstergroesse, wird sie gemerkt, der
    Kontext darauf gekuerzt und einmal neu gesendet. Nennt er keine, bleibt es beim
    Fehler: blind kuerzen und wiederholen kostet nur Zeit.
    """
    try:
        return client.chat.completions.create(model=model, messages=messages, **kwargs)
    except Exception as e:  # noqa: BLE001 — die Absage IST die Information
        provider_id = _provider_id_for_chat()
        if not provider_id:
            raise
        fenster = model_limits.learn_from_error(provider_id, model, e)
        if not fenster:
            raise
        gekuerzt = model_limits.fit_messages(
            messages, model_limits.context_chars(fenster, model_limits.TOOL_SHARE),
        )
        logger.warning(
            "Werkzeug-Kontext war zu gross fuer {}, auf {} Token gekuerzt und wiederholt",
            model, fenster,
        )
        return client.chat.completions.create(model=model, messages=gekuerzt, **kwargs)


def _provider_id_for_chat() -> int | None:
    """Kennung des Anbieters, der die Chat-Route bedient. Die Werkzeuge laufen alle
    ueber dieselbe Route, holen sich ihren Client aber selbst und kennen sie nicht."""
    try:
        from src.services import feature_router
        return (feature_router.resolve("chat").provider or {}).get("id")
    except Exception as e:  # noqa: BLE001 — ohne Kennung wird eben nicht gelernt
        logger.debug("Anbieter der Chat-Route nicht ermittelbar: {}", e)
        return None
