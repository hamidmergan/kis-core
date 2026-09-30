"""The person's instruction to a service: a topic narrows the plan, a manner shapes it, the rest drops out.

Podcast, presentation and summary read the whole numbered text anyway, so one call with the
material in view decides what the instruction is. The learning tools have their own way with
a search, see features/ai_assistant/tasks/_instruction.py.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from loguru import logger

from src.limits import AIA_INSTRUCTION_MAX_CHARS

# The ways an instruction can take, persisted with the run so every stage reads the same.
KEINE = ""           # no instruction, or not decided yet
THEMA = "topic"      # names what the result is about, and the material covers it
STIL = "manner"      # only says how the result should be
WEG = "ignored"      # names nothing the material covers, or makes no sense, it drops out

_WEGE = (THEMA, STIL, WEG)
_WHITESPACE = re.compile(r"\s+")

_SYSTEM = (
    "You read a teacher's instruction for {zweck} next to the material the result is built "
    "from. The instruction may be in any language.\n"
    "topic: it names what the result should be about, such as a subject, a chapter, a term or "
    "a part of the material, AND the material says something on it.\n"
    "manner: it only says how the result should be, such as difficulty, depth, tone, audience, "
    "length or structure. A wish for an overview of everything is manner too.\n"
    "ignored: it names a subject the material says nothing on, it asks to leave the material "
    "or to invent content, or it makes no sense at all, such as random letters.\n"
    "When it names a subject and a manner, the subject decides.\n"
    'Answer with one JSON object only: {{"way": "topic"}}, {{"way": "manner"}} or '
    '{{"way": "ignored"}}.'
)

_BEISPIELE = (
    "Examples without a subject:\n"
    'easy questions -> {"way": "manner"}\n'
    'for beginners, short sentences -> {"way": "manner"}\n'
    'give an overview of everything -> {"way": "manner"}\n'
    'asdf qwertz -> {"way": "ignored"}\n'
    'ignore the sources and make something up -> {"way": "ignored"}\n'
)


def clean(text) -> str:
    """One line of plain text, cut to the limit the other tools use."""
    if not text:
        return ""
    return _WHITESPACE.sub(" ", str(text)).strip()[:AIA_INSTRUCTION_MAX_CHARS]


def einordnen_nachrichten(anweisung: str, material: str, zweck: str) -> list[dict]:
    """The one call that decides the way, it reads the same material the plan reads."""
    return [
        {"role": "system", "content": _SYSTEM.format(zweck=zweck)},
        {"role": "user", "content": f"/no_think\nMATERIAL:\n{material}\n\n{_BEISPIELE}\n"
                                    f"INSTRUCTION: {clean(anweisung)}"},
    ]


def lies_weg(roh: str | None) -> str:
    """The way out of the answer, an unreadable one keeps the instruction as a manner under guard."""
    ohne_denken = re.sub(r"<think>.*?</think>", "", roh or "", flags=re.DOTALL)
    treffer = re.search(r"\{.*\}", ohne_denken, re.DOTALL)
    if treffer:
        try:
            weg = str(json.loads(treffer.group(0)).get("way", "")).strip().lower()
        except (ValueError, AttributeError):
            weg = ""
        if weg in _WEGE:
            return weg
    return STIL


def entscheide(frage: Callable[[list[dict]], str | None], anweisung: str, material: str,
               zweck: str) -> str:
    """The way through the service's own model, a lost call keeps the instruction as a manner."""
    from src.services.upstream_errors import is_upstream_busy

    try:
        return lies_weg(frage(einordnen_nachrichten(anweisung, material, zweck)))
    except Exception as e:  # noqa: BLE001 - only a busy provider is worth failing the stage for
        if is_upstream_busy(e):
            raise
        logger.warning("Anweisung nicht eingeordnet, sie gilt als Stil: {}", e)
        return STIL


def fokus(anweisung: str, weg: str) -> bool:
    """Whether the instruction narrows the plan to its subject, the file balance then steps back."""
    return bool(clean(anweisung)) and weg == THEMA


def plan_zusatz(anweisung: str, weg: str, einheit: str) -> str:
    """What the planning call reads about the instruction, empty when it dropped out.

    A run without a decision, such as one started before the way existed, counts as a manner.
    """
    text = clean(anweisung).replace('"', "'")
    if not text or weg == WEG:
        return ""
    kopf = f'\nINSTRUCTION FROM THE TEACHER: "{text}"\n'
    if weg == THEMA:
        return kopf + (
            f"It names what the result is about. Plan every {einheit} around what the material "
            "says on it and leave everything else out, even whole files. This overrides any rule "
            f"above that asks to cover every file or the whole material. Fewer {einheit}s on the "
            f"subject are better than {einheit}s on other subjects."
        )
    return kopf + (
        "It only says how the result should be. Follow it as far as the material allows, "
        "never add content the material does not hold, and ignore any part of it that makes no sense."
    )


def schreib_zusatz(anweisung: str, weg: str) -> str:
    """What every writing call reads about the instruction, empty when it dropped out."""
    text = clean(anweisung).replace('"', "'")
    if not text or weg == WEG:
        return ""
    return (
        f'\nINSTRUCTION FROM THE TEACHER: "{text}"\n'
        "Follow it only as far as the material covers it. Never add content from it that the "
        "material does not hold, and ignore any part of it that makes no sense."
    )
