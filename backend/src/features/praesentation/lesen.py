"""One read call: a whole source in, facts a slide can be built from out.

The service paces the calls, this module only knows what to ask for and how to read
the answer. Nothing here knows about layouts or slide fields, that belongs to the call
that writes a slide, not to the one that reads a document.
"""

import asyncio

from loguru import logger

from src.limits import (
    PRAESENTATION_CALL_TIMEOUT_SECONDS,
    PRAESENTATION_READ_MAX_ATTEMPTS,
    PRAESENTATION_READ_MAX_OUTPUT_TOKENS,
    PRAESENTATION_READ_MAX_SOURCE_CHARS,
    PRAESENTATION_RETRY_DELAY_SECONDS,
)
from src.services.facts import RateLimited, overloaded, parse_facts
from src.services.model_limits import CHARS_PER_TOKEN

# What one fact is worth of the material budget, and what it costs as JSON with its proof.
# The two differ, budgeting the answer with the first number cuts every long answer off.
CHARS_PER_FACT = 300
_ANSWER_CHARS_PER_FACT = 750

# The search grid of a slide deck. A proof is no category: every fact carries its citation
# in a field of its own, so a category for it would only return the same thing twice.
CATEGORIES_DE: tuple[str, ...] = ("These", "Kernpunkt", "Zahl", "Begriff", "Beispiel", "Ablauf")
CATEGORIES_EN: tuple[str, ...] = ("thesis", "key point", "figure", "term", "example", "process")


def categories(language: str) -> tuple[str, ...]:
    return CATEGORIES_DE if language == "de" else CATEGORIES_EN


FACTS_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "facts",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "facts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "One of the listed categories, verbatim.",
                            },
                            "fact": {
                                "type": "string",
                                "description": (
                                    "The statement in one or two sentences, in the output "
                                    "language, short enough to carry a single point of a "
                                    "slide and complete enough to stand without the document."
                                ),
                            },
                            "citation": {
                                "type": "string",
                                "description": (
                                    "The sentence from the document this rests on, copied "
                                    "word for word in the language of the document."
                                ),
                            },
                            "reference": {
                                "type": "string",
                                "description": (
                                    "Only the label the document gives the part this sits in, "
                                    "such as 'Kapitel 3'. Empty when the document labels nothing."
                                ),
                            },
                        },
                        "required": ["category", "fact", "citation", "reference"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["facts"],
            "additionalProperties": False,
        },
    },
}

# Probed once per process, a provider without the schema mode must not cost every source.
_schema_mode_supported = True


def _rejects_schema(exc: Exception) -> bool:
    """Whether the provider refused the schema mode itself."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status != 400:
        return False
    text = str(exc).casefold()
    return "response_format" in text or "json" in text or "schema" in text


def system_prompt(language: str, grid: tuple[str, ...], max_facts: int) -> str:
    """The reading order: pull out what a deck can be built from, nothing of your own.

    Whoever writes the slides never sees this document, only these statements.
    """
    raster = "\n".join(f"- {k}" for k in grid)
    sprache = "German" if language == "de" else "English"
    return (
        "You prepare ONE document for the team that plans a slide deck for university "
        "teaching. They never see the document itself, only the statements you return.\n"
        f"Rule 1: Write every statement in {sprache}. The document may be in another "
        "language, that never changes your output language.\n"
        "Rule 2: Only what the document states in so many words becomes a statement. Never "
        "invent, never conclude, never interpret.\n"
        "Rule 3: Every statement carries a citation, copied word for word from the document, "
        "in the language of the document. A statement you cannot quote does not exist.\n"
        "Rule 4: A statement stands on its own later, next to other statements from other "
        "documents. Keep a figure with what it counts, a definition with its term, a step "
        "with the procedure it belongs to.\n"
        "Rule 5: Ignore cover pages, headers, footers, page numbers and imprints.\n"
        "Rule 6: The categories below are your search grid. Write the category verbatim, "
        "never one of your own.\n"
        f"Rule 7: Return at most {max_facts} statements. Drop filler and repetition before you "
        "drop substance, and never return the same statement twice.\n"
        "Rule 8: This is one document among several. Never mention that, never refer to the "
        "others, never describe the document as a whole.\n"
        "Rule 9: Do not use semicolons or any type of dash. Use only periods, commas, colons "
        "and question marks.\n"
        f"\nCATEGORIES\n{raster}\n"
    )


def user_prompt(source: dict) -> str:
    """The source itself, named so a refusal can say which one it was.

    Cut at the ceiling: no window takes more whole, and a call that cannot succeed
    would only burn every attempt this source has.
    """
    text = source["content"]
    if len(text) > PRAESENTATION_READ_MAX_SOURCE_CHARS:
        logger.warning("Präsentation: Quelle '{}' hat {} Zeichen, gelesen werden {}",
                       source["filename"], len(text), PRAESENTATION_READ_MAX_SOURCE_CHARS)
        text = text[:PRAESENTATION_READ_MAX_SOURCE_CHARS]
    return f"/no_think\nDocument '{source['source_id']}' ({source['filename']}):\n\n{text}"


async def read_source(client, model: str, *, source: dict, language: str,
                      grid: tuple[str, ...], max_chars: int, max_facts: int,
                      book=None) -> list[dict] | None:
    """The facts of one source, None once every attempt has failed for another reason.

    ``book`` records the consumption of one answer, these calls go around the logged door.
    """
    global _schema_mode_supported
    grenze = max(5, min(max_facts, max_chars // CHARS_PER_FACT))
    nachrichten = [
        {"role": "system", "content": system_prompt(language, grid, grenze)},
        {"role": "user", "content": user_prompt(source)},
    ]
    for versuch in range(1, PRAESENTATION_READ_MAX_ATTEMPTS + 1):
        try:
            # The SDK retries timeouts on its own, one attempt is the only way the limit holds.
            antwort = await client.with_options(max_retries=0).chat.completions.create(
                model=model, messages=nachrichten, temperature=0.1,
                timeout=PRAESENTATION_CALL_TIMEOUT_SECONDS,
                # Sized for the facts actually asked for, not for the budget they count against.
                max_tokens=max(256, min(PRAESENTATION_READ_MAX_OUTPUT_TOKENS,
                                        int(grenze * _ANSWER_CHARS_PER_FACT / CHARS_PER_TOKEN))),
                **({"response_format": FACTS_SCHEMA} if _schema_mode_supported else {}),
            )
            if book is not None:
                book(antwort)
            wahl = antwort.choices[0]
            if getattr(wahl, "finish_reason", None) == "length":
                logger.warning("Präsentation: Antwort zu '{}' lief in den Deckel",
                               source["filename"])
            fakten = parse_facts(wahl.message.content)
            if fakten:
                return fakten[:grenze]
            raise RuntimeError("Das Modell hat keine Fakten geliefert.")
        except Exception as e:  # noqa: BLE001 - one bad source must not sink the deck
            if overloaded(e):
                # The service decides what to do with this, it owns the pacing.
                raise RateLimited(str(e)) from e
            if _schema_mode_supported and _rejects_schema(e):
                logger.warning("Präsentation: Schema-Modus abgelehnt, dieser Prozess fragt ab "
                               "jetzt ohne ({})", e)
                _schema_mode_supported = False
                continue
            if versuch >= PRAESENTATION_READ_MAX_ATTEMPTS:
                logger.warning("Präsentation: Quelle '{}' nach {} Versuch(en) ausgelassen ({})",
                               source["filename"], versuch, e)
                return None
            await asyncio.sleep(PRAESENTATION_RETRY_DELAY_SECONDS)
    return None
