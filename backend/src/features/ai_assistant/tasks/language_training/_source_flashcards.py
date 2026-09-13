"""Flashcards-Generierung aus Quelltext (mode='source')."""

import json

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.features.ai_assistant.prompts.language_training_prompts import AIA_LERNKARTEN_PROMPT

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._title import title_from_items
from src.features.ai_assistant.tasks.language_training._wortteile import clean_word_parts
from src.services.llm_call import create_logged


# Shared keys for the extras of a flashcard.
AIA_FLASHCARD_EXTRAS_FIELDS = (
    "word_parts", "word_parts_explained", "example_sentence",
    "word_class", "singular", "plural",
    "verb_present", "verb_past", "verb_perfect"
)


def flashcard_extras(c: dict, begriff: str) -> dict:
    """The extras of a flashcard, shared by the source text and glossary paths."""
    extras = {
        k: (c.get(k) or "").strip()
        for k in AIA_FLASHCARD_EXTRAS_FIELDS
        if (c.get(k) or "").strip()
    }
    parts, explained = clean_word_parts(
        begriff, extras.get("word_parts", ""), extras.get("word_parts_explained", ""))
    if extras.get("word_parts") and not parts:
        # So it stays visible how often the model gets it wrong.
        logger.info("Lernkarte {}: Wortzerlegung {!r} verworfen, ein Teil steht nicht im Begriff",
                    begriff, extras["word_parts"])
    for schluessel, wert in (("word_parts", parts), ("word_parts_explained", explained)):
        if wert:
            extras[schluessel] = wert
        else:
            extras.pop(schluessel, None)
    return extras


def generate_flashcards_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    locale: str = "de",
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
) -> tuple[list[dict], str]:
    # Explanations follow the language, the term stays in the source language.
    prompt = (
        AIA_LERNKARTEN_PROMPT.replace("{count}", str(count)).replace("{language}", language)
        + adaptive_suffix + title_avoidance + coverage
    )
    # No block with existing cards, the model would just copy them.
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": (
            f"Create flashcards from {ctx.source_hint}. Write the explanations in {language}, "
            f"keep the term itself in the source-text language:\n\n{ctx.context}"
        )},
    ]
    # 0.6 for some word variety, the real variation comes from the context.
    response = create_logged(client, endpoint="lernkarten", model=model, messages=messages, temperature=0.6)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    data = json.loads(answer)

    cards = (data.get("cards") or [])[:count]
    items = [_format_lernkarte(c) for c in cards]
    # One batched attribution for the whole set, exactly one source per card.
    attach_chips(items, [_card_claim(c) for c in cards], ctx, multi=False)
    # The title comes from the same answer, that saves a second call.
    title = (data.get("title") or "").strip()
    if not title:
        title = title_from_items(client, model, items, ctx.multi_label)
    return items, title


def _format_lernkarte(c: dict) -> dict:
    """Maps the model card onto front and back, citations are added later."""
    item = {
        "front": (c.get("begriff") or "").strip(),
        "back": (c.get("definition") or "").strip(),
        "back_en": (c.get("begriff_en") or "").strip(),
        # Which section the model claims to have used, not stored.
        "_section": c.get("section"),
    }
    extras = flashcard_extras(c, item["front"])
    if extras:
        item["extras"] = extras
    return item


def _card_claim(c: dict) -> str:
    """Text attributed back to the source: the term plus its definition."""
    begriff = (c.get("begriff") or "").strip()
    definition = (c.get("definition") or "").strip()
    claim = f"{begriff}: {definition}".strip(": ").strip()
    return claim or begriff
