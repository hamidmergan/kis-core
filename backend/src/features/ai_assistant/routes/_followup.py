"""Makes a follow-up question self-contained before the search, inside the pre-call that runs anyway."""

import json
import re
from typing import Optional

from ._helpers import _strip_inline_citation_chips

KEINE = "none"
UMSCHREIBEN = "rewrite"
UMFORMEN = "reformat"

# Only short inputs are read as a follow-up question.
MAX_NACHFRAGE_WOERTER = 15

# The last round is a clue, not material.
_MAX_ANTWORT_ZEICHEN = 1200
_MAX_FRAGE_ZEICHEN = 300


def lohnt_nachschlagen(frage: str, quelltext: Optional[str] = None) -> bool:
    """Is it worth fetching the last round for this input at all?"""
    if quelltext:
        return False
    return len((frage or "").split()) <= MAX_NACHFRAGE_WOERTER


def ist_nachfrage_moeglich(
    frage: str, letzte_runde: Optional[dict], quelltext: Optional[str] = None
) -> bool:
    """Can this input be a follow-up question at all?"""
    from src.features.ai_assistant.prompts.refusal_prompts import is_sentinel_refusal

    if quelltext:
        return False
    if not letzte_runde:
        return False
    antwort = (letzte_runde.get("answer") or "").strip()
    if not antwort:
        return False
    # A pure refusal names no topic, the follow-up then stays as it is.
    if is_sentinel_refusal(antwort):
        return False
    return len((frage or "").split()) <= MAX_NACHFRAGE_WOERTER


def verlaufsblock(letzte_runde: dict) -> str:
    """The last round as a short block for the pre-call, without source chips."""
    frage = (letzte_runde.get("question") or "").strip()[:_MAX_FRAGE_ZEICHEN]
    antwort = _strip_inline_citation_chips(letzte_runde.get("answer") or "").strip()
    antwort = antwort[:_MAX_ANTWORT_ZEICHEN]
    return (
        "PREVIOUS TURN OF THIS CHAT (context only, never answer it again):\n"
        f"Previous question: {frage}\n"
        f"Previous answer (may be truncated): {antwort}"
    )


def vorcall_eingabe(frage: str, letzte_runde: Optional[dict]) -> str:
    """The user message of the pre-call, the new line comes last."""
    if not letzte_runde:
        return frage
    return f"{verlaufsblock(letzte_runde)}\n\nNEW LINE FROM THE USER:\n{frage}"


def umform_nachrichten(
    letzte_runde: dict, anweisung: str, chat_lang: str,
    vorherige_fragen: list[str], zusatz: str,
) -> list[dict]:
    """The two messages for reshaping the last answer."""
    from src.features.ai_assistant.prompts.rag_chat import (
        aia_reformat_user_message,
        aia_system_reformat,
    )

    text = _strip_inline_citation_chips(letzte_runde.get("answer") or "").strip()
    return [
        {"role": "system", "content": aia_system_reformat(chat_lang, vorherige_fragen)},
        {"role": "user", "content": aia_reformat_user_message(text, anweisung) + zusatz},
    ]


def letzte_quellen(
    letzte_runde: dict, uuid_zu_id: dict
) -> tuple[list[dict], dict, dict, list[dict]]:
    """Reuses the source references of the last round, reshaping does not search."""
    qmap = [q for q in (letzte_runde.get("source_qmap") or [])
            if q.get("uuid") in uuid_zu_id]
    id_zu_qnum = {uuid_zu_id[q["uuid"]]: q["qnum"] for q in qmap}
    seiten = [s for s in (letzte_runde.get("source_pages") or [])
              if s.get("source_uuid") in uuid_zu_id]
    gesehen: dict[int, set] = {}
    for eintrag in seiten:
        sid = uuid_zu_id[eintrag["source_uuid"]]
        menge = gesehen.setdefault(sid, set())
        # Audio and video are checked at source level, their page number is no jump target.
        if eintrag.get("start_time") is None and eintrag.get("page_number") is not None:
            menge.add(eintrag["page_number"])
    return qmap, id_zu_qnum, gesehen, seiten


def _json_objekt(roh: str) -> Optional[dict]:
    """First JSON object from a model answer, tolerant of fences and thinking blocks."""
    text = re.sub(r"<think>.*?</think>", "", roh or "", flags=re.DOTALL)
    text = text.replace("```json", "").replace("```", "")
    treffer = re.search(r"\{.*\}", text, re.DOTALL)
    if not treffer:
        return None
    try:
        obj = json.loads(treffer.group(0))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def nachfrage_lesen(roh: str, frage: str) -> tuple[str, str]:
    """Kind and question from the pre-call answer, unchanged when in doubt."""
    obj = _json_objekt(roh)
    if not obj:
        return KEINE, frage
    art = str(obj.get("followup") or "").strip().lower()
    if art not in (UMSCHREIBEN, UMFORMEN):
        return KEINE, frage
    eigenstaendig = str(obj.get("standalone") or "").strip()
    if not eigenstaendig:
        return KEINE, frage
    return art, eigenstaendig
