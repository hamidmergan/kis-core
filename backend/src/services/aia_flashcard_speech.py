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
    ein Absturz.
    """
    raw_provider = (db.get_setting(_PROVIDER_KEY, "") or "").strip()
    voice = (db.get_setting(_VOICE_KEY, "") or "").strip()
    if not raw_provider or not voice:
        return None
    try:
        provider_id = int(raw_provider)
    except ValueError:
        return None
    return provider_id, voice


def speech_enabled() -> bool:
    """Ob die Ansicht den Lautsprecher zeigen soll."""
    return configured_voice() is not None
