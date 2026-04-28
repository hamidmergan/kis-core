"""Flashcards-Generierung aus Quelltext (mode='source')."""

import json

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.tool_prompts import KIA_LERNKARTEN_PROMPT

from src.features.ai_assistant.tasks.language_training._card_base import parse_card, with_avoid
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._title import title_from_items


def generate_flashcards_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    existing_fronts: list[str],
) -> tuple[list[dict], str]:
    prompt = KIA_LERNKARTEN_PROMPT.replace("{count}", str(count))
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": with_avoid(
            existing_fronts,
            f"Create flashcards from {ctx.source_hint} (respond in the source-text language):\n\n{ctx.context}",
        )},
    ]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    data = json.loads(answer)

    items = [_format_lernkarte(ctx, c) for c in data.get("cards", [])][:count]
    title = title_from_items(client, model, items, ctx.multi_label)
    return items, title


def _format_lernkarte(ctx: QuelleContext, c: dict) -> dict:
    """Formatiert Lernkarte: Begriff/Definition in front/back-Spalten, Rest in extras JSONB."""
    begriff = (c.get("begriff") or "").strip()
    definition = (c.get("definition") or "").strip()
    # Map semantic names to shared DB columns (front/back) so the cards logic stays unchanged
    normalized = {
        "front": begriff,
        "back": definition,
        "back_en": (c.get("begriff_en") or "").strip(),
        "source_label": c.get("source_label"),
        "page_number": c.get("page_number"),
    }
    item = parse_card(ctx, normalized, include_back_en=True, search_term=begriff, multi_source=True)
    extras = {
        k: (c.get(k) or "").strip()
        for k in ("word_parts", "word_parts_explained", "example_sentence")
        if (c.get(k) or "").strip()
    }
    if extras:
        item["extras"] = extras
    return item
