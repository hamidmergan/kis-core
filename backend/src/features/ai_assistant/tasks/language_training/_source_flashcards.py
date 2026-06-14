"""Flashcards-Generierung aus Quelltext (mode='source')."""

import json

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.tool_prompts import AIA_LERNKARTEN_PROMPT

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips
from src.features.ai_assistant.tasks.language_training._card_base import with_avoid
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._title import title_from_items


def generate_flashcards_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    existing_fronts: list[str],
    locale: str = "de",
) -> tuple[list[dict], str]:
    # Explanations follow the UI language; the term itself (begriff) stays in the
    # source language for study and highlighting (see prompt LANGUAGE rule).
    language = "English" if (locale or "").lower().startswith("en") else "German"
    prompt = AIA_LERNKARTEN_PROMPT.replace("{count}", str(count)).replace("{language}", language)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": with_avoid(
            existing_fronts,
            f"Create flashcards from {ctx.source_hint}. Write the explanations in {language}, "
            f"keep the term itself in the source-text language:\n\n{ctx.context}",
        )},
    ]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    data = json.loads(answer)

    cards = (data.get("cards") or [])[:count]
    items = [_format_lernkarte(c) for c in cards]
    # One batched attribution for the whole set: each card cites where its term+definition
    # actually appears (same pgvector gate as chat), nav-only, no highlight. multi=True so a
    # term genuinely defined across two passages keeps both, but never "every page with the word".
    attach_chips(items, [_card_claim(c) for c in cards], ctx, multi=True)
    title = title_from_items(client, model, items, ctx.multi_label)
    return items, title


def _format_lernkarte(c: dict) -> dict:
    """Map the LLM card to shared DB columns (front/back). Source attribution is added
    afterwards by attach_chips, not guessed here."""
    item = {
        "front": (c.get("begriff") or "").strip(),
        "back": (c.get("definition") or "").strip(),
        "back_en": (c.get("begriff_en") or "").strip(),
    }
    extras = {
        k: (c.get(k) or "").strip()
        for k in ("word_parts", "word_parts_explained", "example_sentence")
        if (c.get(k) or "").strip()
    }
    if extras:
        item["extras"] = extras
    return item


def _card_claim(c: dict) -> str:
    """Text attributed back to the source: the term plus its definition."""
    begriff = (c.get("begriff") or "").strip()
    definition = (c.get("definition") or "").strip()
    claim = f"{begriff}: {definition}".strip(": ").strip()
    return claim or begriff
