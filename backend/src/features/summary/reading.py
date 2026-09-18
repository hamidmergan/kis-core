"""Map phase: one call per unit, steered by the build plan, capped in what it returns."""

import asyncio

from loguru import logger

from src.features.summary.models import GROUND_RULES, Caller
from src.limits import SUMMARY_READ_MAX_ATTEMPTS, SUMMARY_RETRY_DELAY_SECONDS
from src.services.model_limits import CHARS_PER_TOKEN

# A German word with its space, so a character budget becomes a word count.
_CHARS_PER_WORD = 7


def system_prompt(language: str, template_body: str, max_chars: int,
                  part: int = 1, parts: int = 1) -> str:
    """The reading order, an excerpt of a file gets its own opening and closing rule."""
    ausschnitt = parts > 1
    woerter = max(100, max_chars // _CHARS_PER_WORD)
    return (
        "You pull the usable substance out of ONE document for a writer who never sees "
        "the document itself. The writer will follow the BUILD PLAN below, so what that "
        "plan needs comes first and in full.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Take everything the build plan asks for, then everything else that carries "
        "the argument: figures, quantities, dates, deadlines, proper names, definitions, "
        "quotable sentences and the reasoning that connects them. Drop filler and repetition.\n"
        "Rule 9: Never separate a figure, a date or a quantity from what it refers to.\n"
        "Rule 10: Keep a definition with its term and a quotation with who said it.\n"
        "Rule 11: Keep whatever the document marks as open, disputed or uncertain, and say "
        "that it is open.\n"
        + (
            "Rule 12: Open with two or three sentences saying what THIS EXCERPT covers. Then "
            "dense bullet points, one statement each. No headings, no closing remark.\n"
            if ausschnitt else
            "Rule 12: Open with two or three sentences saying what this document is about and "
            "where it leads. Then dense bullet points, one statement each. No headings, no "
            "closing remark.\n"
        )
        + f"Rule 13: Stay under {woerter} words, the answer is cut off beyond that. Put what "
        "the build plan needs first, never drop a fact to save words elsewhere.\n"
        + (
            f"Rule 14: The text below is excerpt {part} of {parts} of ONE longer file, other "
            "files are read alongside it. It may begin or end mid topic, that is expected. "
            "Work strictly on what you are given, never guess what stands before or after, and "
            "never call a term undefined merely because its definition is not in your excerpt. "
            "Never describe it as a document of its own, never announce that it is an excerpt.\n"
            if ausschnitt else
            "Rule 14: This is one document among several. Never announce that and never refer "
            "to the others.\n"
        )
        + "\nBUILD PLAN\n" + template_body
    )


def user_prompt(unit: dict) -> str:
    """The unit itself, its id travels so its facts stay attributable."""
    if unit.get("parts", 1) > 1:
        wie = f"{unit['filename']}, excerpt {unit['part']} of {unit['parts']}"
    else:
        wie = unit["filename"]
    return f"/no_think\nDocument '{unit['source_id']}' ({wie}):\n\n{unit['content']}"


def cut_to_last_line(text: str) -> str:
    """Drops a bullet the cap cut in half, unless that would drop most of the text."""
    schnitt = text.rfind("\n")
    return text[:schnitt].rstrip() if schnitt > len(text) // 2 else text


async def read_unit(caller: Caller, *, unit: dict, language: str,
                    template_body: str, max_chars: int) -> str | None:
    """The facts of one unit, or None once every attempt has failed."""
    for versuch in range(1, SUMMARY_READ_MAX_ATTEMPTS + 1):
        try:
            antwort = await caller.create(
                messages=[
                    {"role": "system", "content": system_prompt(
                        language, template_body, max_chars,
                        unit.get("part", 1), unit.get("parts", 1))},
                    {"role": "user", "content": user_prompt(unit)},
                ],
                temperature=0.2,
                max_tokens=max(256, int(max_chars / CHARS_PER_TOKEN)),
            )
            wahl = antwort.choices[0]
            text = (wahl.message.content or "").strip()
            if getattr(wahl, "finish_reason", None) == "length":
                text = cut_to_last_line(text)
            if text:
                return text
            raise RuntimeError("Das Modell hat nichts geantwortet.")
        except Exception as e:  # noqa: BLE001 - one bad unit must not sink the run
            if versuch >= SUMMARY_READ_MAX_ATTEMPTS:
                logger.warning("Zusammenfassung: Einheit '{}' nach {} Versuch(en) ausgelassen ({})",
                               unit.get("label", unit["source_id"]), versuch, e)
                return None
            await asyncio.sleep(SUMMARY_RETRY_DELAY_SECONDS)
    return None
