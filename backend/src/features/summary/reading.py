"""Map phase: one call per file, the whole file, answered as a list of facts with proof."""

import asyncio

from loguru import logger

from src.features.summary.facts import parse_facts
from src.features.summary.models import GROUND_RULES, Caller
from src.limits import SUMMARY_READ_MAX_ATTEMPTS, SUMMARY_RETRY_DELAY_SECONDS
from src.services.model_limits import CHARS_PER_TOKEN

# One fact with its proof, measured on the answers of the accepted run.
_CHARS_PER_FACT = 300

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
                                    "language, with every figure next to what it refers to."
                                ),
                            },
                            "citation": {
                                "type": "string",
                                "description": (
                                    "The sentence from the document this rests on, copied "
                                    "word for word in the language of the document."
                                ),
                            },
                        },
                        "required": ["category", "fact", "citation"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["facts"],
            "additionalProperties": False,
        },
    },
}

# Probed once per process, a provider without the schema mode must not cost every file.
_schema_mode_supported = True


class RateLimited(Exception):
    """The provider turned the call away or let it run out, the run slows down."""


def overloaded(exc: Exception) -> bool:
    """Whether this failure means too much at once rather than a bad request."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (429, 503):
        return True
    if isinstance(exc, asyncio.TimeoutError):
        return True
    return "timeout" in type(exc).__name__.casefold()


def _rejects_schema(exc: Exception) -> bool:
    """Whether the provider refused the schema mode itself."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status != 400:
        return False
    text = str(exc).casefold()
    return "response_format" in text or "json" in text or "schema" in text


def system_prompt(language: str, template_body: str, categories: tuple[str, ...],
                  max_facts: int) -> str:
    """The reading order: pull out what the build plan needs, nothing of your own."""
    raster = "\n".join(f"- {k}" for k in categories)
    return (
        "You are a strict extractor. You pull statements out of ONE document for a writer "
        "who never sees the document itself.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Never invent, never interpret, never conclude. Only what the document "
        "states in so many words becomes a fact.\n"
        "Rule 9: Every fact carries a citation, copied word for word from the document, in "
        "the language of the document. A fact you cannot quote does not exist. One sentence "
        "of citation is enough, never a whole paragraph.\n"
        "Rule 10: Never separate a figure, a date or a quantity from what it refers to, keep "
        "a definition with its term and a quotation with who said it.\n"
        "Rule 11: Whatever the document marks as open, disputed or uncertain is a fact of "
        "its own, and says that it is open.\n"
        "Rule 12: The categories below are your search grid. Take what they ask for first "
        "and in full, then everything else that carries the argument. Write the category "
        "verbatim, never a category of your own.\n"
        f"Rule 13: Return at most {max_facts} facts. Drop filler and repetition before you "
        "drop substance, and never return the same statement twice.\n"
        "Rule 14: This is one document among several. Never mention that, never refer to "
        "the others, never describe the document as a whole.\n"
        f"\nCATEGORIES\n{raster}\n"
        "\nThe writer follows the build plan below. What it needs comes first.\n\n"
        "BUILD PLAN\n" + template_body
    )


def user_prompt(source: dict) -> str:
    """The file itself, named so a refusal can say which one it was."""
    return f"/no_think\nDocument '{source['source_id']}' ({source['filename']}):\n\n{source['content']}"


async def read_source(caller: Caller, *, source: dict, language: str, template_body: str,
                      categories: tuple[str, ...], max_chars: int) -> list[dict] | None:
    """The facts of one file, None once every attempt has failed for another reason."""
    global _schema_mode_supported
    max_facts = max(5, max_chars // _CHARS_PER_FACT)
    nachrichten = [
        {"role": "system",
         "content": system_prompt(language, template_body, categories, max_facts)},
        {"role": "user", "content": user_prompt(source)},
    ]
    for versuch in range(1, SUMMARY_READ_MAX_ATTEMPTS + 1):
        try:
            antwort = await caller.create(
                messages=nachrichten,
                temperature=0.1,
                max_tokens=max(256, int(max_chars / CHARS_PER_TOKEN)),
                **({"response_format": FACTS_SCHEMA} if _schema_mode_supported else {}),
            )
            wahl = antwort.choices[0]
            if getattr(wahl, "finish_reason", None) == "length":
                logger.warning("Zusammenfassung: Antwort zu '{}' lief in den Deckel",
                               source["filename"])
            fakten = parse_facts(wahl.message.content)
            if fakten:
                return fakten[:max_facts]
            raise RuntimeError("Das Modell hat keine Fakten geliefert.")
        except Exception as e:  # noqa: BLE001 - one bad file must not sink the run
            if overloaded(e):
                # The pipeline decides what to do with this, it owns the concurrency.
                raise RateLimited(str(e)) from e
            if _schema_mode_supported and _rejects_schema(e):
                logger.warning("Zusammenfassung: Schema-Modus abgelehnt, dieser Prozess "
                               "fragt ab jetzt ohne ({})", e)
                _schema_mode_supported = False
                continue
            if versuch >= SUMMARY_READ_MAX_ATTEMPTS:
                logger.warning("Zusammenfassung: Datei '{}' nach {} Versuch(en) ausgelassen ({})",
                               source["filename"], versuch, e)
                return None
            await asyncio.sleep(SUMMARY_RETRY_DELAY_SECONDS)
    return None
