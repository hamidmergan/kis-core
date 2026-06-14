"""Karteikarten (Q&A cards) from source (mode='source').

ONE LLM call generates the question AND the answer together; source links are then
attached post-hoc by the shared pgvector attribution (same gate as chat), nav-only.
This replaces the old N+1 two-pass (one call per card through the chat pipeline)."""

import json

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.tool_prompts import AIA_KARTEIKARTEN_QA_PROMPT

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips
from src.features.ai_assistant.tasks.language_training._card_base import with_avoid
from src.features.ai_assistant.tasks.language_training._context import QuelleContext


def _language_label(locale: str) -> str:
    return "English" if (locale or "").lower().startswith("en") else "German"


def generate_cards_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    existing_fronts: list[str],
    locale: str = "de",
) -> tuple[list[dict], str]:
    language = _language_label(locale)
    prompt = (
        AIA_KARTEIKARTEN_QA_PROMPT
        .replace("{count}", str(count))
        .replace("{language}", language)
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": with_avoid(
            existing_fronts,
            f"Generate {count} question-answer cards from {ctx.source_hint} "
            f"(write them in {language}, regardless of the source-text language):\n\n{ctx.context}",
        )},
    ]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    try:
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
    except json.JSONDecodeError as e:
        logger.error("Karteikarten QA JSON parse failed: {}", e)
        return [], ctx.multi_label

    title = (data.get("title") or "").strip() or ctx.multi_label
    cards = [
        c for c in (data.get("cards") or [])
        if isinstance(c, dict)
        and (c.get("question") or "").strip()
        and (c.get("answer") or "").strip()
    ][:count]
    if not cards:
        return [], title

    items = [{"front": c["question"].strip(), "back": c["answer"].strip()} for c in cards]
    claims = [f'{c["question"].strip()} {c["answer"].strip()}'.strip() for c in cards]
    # A card is one atomic Q+A, so multi=False -> exactly the single best-matching source.
    attach_chips(items, claims, ctx, multi=False)

    return items, title
