"""Shared helpers for KI-Assistent Celery tasks."""

import re

from langfuse.decorators import langfuse_context


def _format_ts(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


# Die Sprache, in der die Werkzeuge ihre Aufgaben erzeugen, wenn der Kursraum nichts
# anderes sagt. Deutsch, weil KIS an deutschen Hochschulen zum Deutschlernen benutzt wird.
TOOL_OUTPUT_LANGUAGE = "German"


def tool_output_language(workspace_id) -> tuple[str, str]:
    """(Sprachcode, englischer Sprachname) fuer die erzeugten Inhalte dieses Kursraums.

    NICHT die Oberflaechensprache der Person. Ein Deutschkurs bleibt ein Deutschkurs, auch
    wenn jemand die Oberflaeche auf Englisch stellt; sonst bekaeme ein Lernender eine
    englische Passiv-Uebung, an der es nichts zu ueben gibt. Statische Oberflaechentexte
    folgen weiter der Sprachwahl, nur der erzeugte Inhalt nicht.

    Die Sprache steht am Kursraum (``diagnosis_language``, Standard 'de'), und der Owner
    setzt sie. Bewusst keine Erkennung aus der Quelle: eine Hochschule, die auf Franzoesisch
    unterrichtet, stellt es einmal ein, und ein englisches Paper in einem Deutschkurs soll
    die Uebungssprache nicht umwerfen.

    Ist der Kursraum unbekannt oder nicht lesbar, gilt der Standard. Ein aelterer
    eingereihter Auftrag ohne Kursraum bekommt also Deutsch statt eines Fehlers.
    """
    from src.i18n import DEFAULT_DIAGNOSIS_LANGUAGE, TRANSCRIPT_LANGUAGES

    code = DEFAULT_DIAGNOSIS_LANGUAGE
    if workspace_id:
        from src import database as db
        try:
            workspace = db.get_aia_workspace_by_id(workspace_id) or {}
            code = workspace.get("diagnosis_language") or DEFAULT_DIAGNOSIS_LANGUAGE
        except Exception:  # noqa: BLE001 - der Standard ist eine brauchbare Antwort
            pass
    if code not in TRANSCRIPT_LANGUAGES:
        # Ein Wert, den niemand mehr anbietet. Dann faellt AUCH der Code zurueck: sonst
        # wuerde weiter unten eine Grammatikregel unter einem Code abgelegt, den kein
        # Leser je wieder anfragt.
        code = DEFAULT_DIAGNOSIS_LANGUAGE
    return code, TRANSCRIPT_LANGUAGES[code]["name"]


def _get_llm_client():
    """Return (client, model, provider) using the configured LLM provider."""
    from langfuse.openai import OpenAI
    from src.dependencies import _resolve_llm_provider
    _api_key, _base_url, _model, _provider = _resolve_llm_provider()
    from src.features.ai_assistant.tasks._retry import RetryingClient
    # max_retries=0 bleibt: die eingebaute Wiederholung des SDK unterscheidet nicht
    # zwischen einer abgerissenen Verbindung und einer Absage wegen Überlastung, und
    # eine 429 nachzuschlagen verschärft den hochschulweit geteilten Engpass. Die
    # Unterscheidung trifft RetryingClient.
    client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=120)
    langfuse_context.update_current_observation(
        metadata={"provider": _provider, "base_url": _base_url, "model": _model},
    )
    return RetryingClient(client), _model, _provider


def _clean_llm_json(text: str) -> str:
    """Strip markdown fences and leading/trailing whitespace from LLM JSON output."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()
