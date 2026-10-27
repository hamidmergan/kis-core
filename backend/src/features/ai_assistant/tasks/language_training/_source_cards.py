"""Quiz cards from the sources, question and answer in one call."""

import json

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.features.ai_assistant.prompts.language_training_prompts import (
    AIA_KARTEIKARTEN_QA_PROMPT,
)

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._hint import attach_hint
from src.features.ai_assistant.tasks._context_budget import exercise_max_tokens
from src.features.ai_assistant.prompts.language_training_prompts import COMPACT_JSON_RULE
from src.features.ai_assistant.tasks._json_commas import loads_entries
from src.services.llm_call import create_logged


def generate_cards_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    locale: str = "de",
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
    instruction: str = "",
) -> tuple[list[dict], str]:
    # adaptive_suffix pitches question + answer at the learner's CEFR level.
    prompt = (
        AIA_KARTEIKARTEN_QA_PROMPT
        .replace("{count}", str(count))
        .replace("{language}", language)
    ) + adaptive_suffix + title_avoidance + coverage + COMPACT_JSON_RULE + instruction
    # No block with existing cards, the model would just copy them.
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": (
            f"Generate {count} question-answer cards from {ctx.source_hint} "
            f"(write them in {language}, regardless of the source-text language):\n\n{ctx.context}"
        )},
    ]
    # 0.6 for some word variety, the real variation comes from the context.
    response = create_logged(client, endpoint="karteikarten", model=model, messages=messages, temperature=0.6,
                             max_tokens=exercise_max_tokens(count))
    try:
        data = loads_entries(_clean_llm_json(response.choices[0].message.content or ""), "cards")
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
    # The hint comes from the same answer and not from a second call.
    for item, c in zip(items, cards):
        attach_hint(item, c)
    claims = [f'{c["question"].strip()} {c["answer"].strip()}'.strip() for c in cards]
    # A card is one atomic Q+A, so multi=False -> exactly the single best-matching source.
    attach_chips(items, claims, ctx, multi=False)

    return items, title
