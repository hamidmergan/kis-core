"""Ein Modellaufruf, dessen Antwort JSON sein soll.

Herausgeloest, damit die Einstufung (Abschlussbewertung) und der Adminbereich
(Fragen erzeugen) dieselbe Anbindung benutzen statt zweier Kopien. Der eine Punkt,
der hier wirklich haengt, ist der JSON-Modus: nicht jeder eingerichtete Anbieter
nimmt ``response_format``, und wer ihn ablehnt, soll nicht bei jedem Aufruf erneut
einen abgelehnten Aufruf kosten. Deshalb wird einmal je Prozess geprobt.
"""

import asyncio

from fastapi import HTTPException
from loguru import logger

from src.i18n import t

# Einmal je Prozess geprobt statt bei jedem Aufruf erneut.
_json_mode_supported = True


def _rejects_json_mode(exc: Exception) -> bool:
    """True, wenn der Anbieter ``response_format`` selbst abgelehnt hat.

    Absichtlich eng: nur ein 400, der das Feld auch benennt, zaehlt. Ein 429 oder
    ein 400 wegen Kontextlaenge darf den JSON-Modus nicht fuer den ganzen Prozess
    abschalten.
    """
    if getattr(exc, "status_code", None) != 400:
        return False
    text = str(exc).lower()
    return "response_format" in text or "json" in text


def _create(llm, messages: list[dict], *, json_mode: bool):
    kwargs = {
        "model": llm._model,
        "messages": messages,
        "temperature": 0.4,
        **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return llm._client.chat.completions.create(**kwargs)


def call_json_llm(llm, messages: list[dict]):
    """Ein Durchlauf, im JSON-Modus wo der Anbieter ihn kann.

    Der JSON-Modus zaehlt hier mehr als anderswo: der Prompt verlangt zugleich
    Fliesstext-Ton und JSON, und ohne die Fessel driftet das Modell oft genug in
    reine Prosa ab, dass der Reparaturdurchlauf regelmaessig feuert und das
    Aufrufvolumen gegen ein geteiltes Limit verdoppelt.
    """
    global _json_mode_supported
    if _json_mode_supported:
        try:
            return _create(llm, messages, json_mode=True)
        except Exception as exc:
            if not _rejects_json_mode(exc):
                raise
            logger.warning("JSON-Modus vom Anbieter abgelehnt, dieser Prozess "
                           "fragt ab jetzt ohne: {}", exc)
            _json_mode_supported = False
    return _create(llm, messages, json_mode=False)


async def ask_json(llm, messages: list[dict], *, locale: str, what: str) -> str:
    """Der Aufruf in einem Thread, mit einer verstaendlichen Absage bei Ausfall.

    ``what`` steht nur im Log und sagt, welcher Aufruf gescheitert ist.
    """
    try:
        response = await asyncio.to_thread(call_json_llm, llm, messages)
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("{} LLM call failed: {}", what, exc)
        raise HTTPException(status_code=502,
                            detail=t("ai.languageDiagnosis.llmUnavailable", locale))
