"""Karteikarten (Q&A cards) from source (mode='source').

ONE LLM call generates the question AND the answer together; source links are then
attached post-hoc by the shared pgvector attribution (same gate as chat), nav-only.
This replaces the old N+1 two-pass (one call per card through the chat pipeline)."""

import json

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.features.ai_assistant.prompts.language_training_prompts import (
    AIA_KARTEIKARTEN_QA_PROMPT,
)

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._hint import attach_hint
from src.services.llm_context_healing import create_with_shrink


def generate_cards_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    locale: str = "de",
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
) -> tuple[list[dict], str]:
    # adaptive_suffix pitches question + answer at the learner's CEFR level.
    prompt = (
        AIA_KARTEIKARTEN_QA_PROMPT
        .replace("{count}", str(count))
        .replace("{language}", language)
    ) + adaptive_suffix + title_avoidance + coverage
    # No "avoid these existing cards" block: feeding them back made the model copy them.
    # Variation comes from the context sweep in build_source_context, and a repeat that
    # still gets through is dropped afterwards by _dedup. Only the
    # TITLE gets a do-not-repeat list (title_avoidance), which has no such pull.
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": (
            f"Generate {count} question-answer cards from {ctx.source_hint} "
            f"(write them in {language}, regardless of the source-text language):\n\n{ctx.context}"
        )},
    ]
    # 0.6 for a little wording diversity; the real variation is the context sweep in
    # build_source_context (different chunks per run). Still JSON-safe.
    response = create_with_shrink(client, model=model, messages=messages, temperature=0.6)
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

    items = [{"front": c["question"].strip(), "back": c["answer"].strip(),
              # See _source_mc: the model's own section number, for the coverage check.
              "_section": c.get("section")} for c in cards]
    # Der Tipp kommt aus derselben Antwort und nicht aus einem zweiten Aufruf.
    for item, c in zip(items, cards):
        attach_hint(item, c)
    claims = [f'{c["question"].strip()} {c["answer"].strip()}'.strip() for c in cards]
    # A card is one atomic Q+A, so multi=False -> exactly the single best-matching source.
    attach_chips(items, claims, ctx, multi=False)

    return items, title
