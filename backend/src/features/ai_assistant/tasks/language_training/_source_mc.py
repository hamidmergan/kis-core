"""MC-basierte Tools (lueckentext, quiz, vokabeltest) aus Quelltext (mode='source')."""

import json

from src.features.ai_assistant.tasks._helpers import _clean_llm_json, _language_label

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._title import title_from_items


_SOURCE_RULE = (
    "- For every question, include source_label and page_number, the source/page the content came from.\n"
)
_PERSONAL_RULE = (
    "IMPORTANT:\n- Do NOT use personal names in questions. Instead of 'laut Prof. X', write 'laut Quelle' (German) or 'according to the source' (English), matching the output language.\n"
)
# The title ships with the generation response so no extra LLM call is needed for it
# (that call used to come back empty on reasoning models and left the raw filename behind).
_TITLE_RULE = (
    "- title: a short, concrete topic title in {language} (max 6 words), no quotation marks, "
    "never a filename.\n"
)


def generate_mc_from_source(
    client, model,
    ctx: QuelleContext,
    tool: str,
    count: int,
    locale: str = "de",
) -> tuple[list[dict], str]:
    language = _language_label(locale)
    tool_prompt = _build_prompt(tool, count, language)
    # No "already exists, avoid these" block: feeding the old questions back made the model
    # COPY them verbatim (it even reproduced a "laut Seite 7" question for a page no longer in
    # context). Variation comes instead from the rotating page subset in build_source_context.
    messages = [
        {"role": "system", "content": tool_prompt},
        {"role": "user", "content": f"Write the output in {language}.\n\nSources:\n\n{ctx.context}"},
    ]
    # 0.6 (not 0.3): a little sampling diversity for wording. The real variation comes from the
    # rotating page subset in build_source_context (different chunks per run). Still JSON-safe.
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.6)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    data = json.loads(answer)
    # Preferred shape is {"title": ..., "exercises": [...]} so the title comes free with the
    # generation call. A bare array (older/simpler models) still works, then the title is
    # derived afterwards from the items.
    if isinstance(data, dict):
        exercises = data.get("exercises") or []
        json_title = (data.get("title") or "").strip()
    else:
        exercises = data
        json_title = ""
    exercises = list(exercises)[:count]

    if tool == "lueckentext":
        items, claims = _build_lueckentext_items(exercises)
    else:  # quiz + vokabeltest
        items, claims = _build_quiz_items(exercises)

    # Post-hoc attribution (same pgvector gate as chat): each item cites where its
    # answer actually appears, nav-only, no highlight. The LLM's source_label/page_number
    # (asked for above) are intentionally ignored — attribution decides the real page.
    # multi=False: an MC answer has a single origin, not "every page with the word".
    attach_chips(items, claims, ctx, multi=False)

    title = json_title or title_from_items(client, model, items, ctx.multi_label)
    return items, title


def _build_prompt(tool: str, count: int, language: str) -> str:
    base = (
        f"You create exercises based on the given source text. "
        f"Write ALL questions, sentences, options, and answers in {language}, "
        f"regardless of the source-text language. Translate source content into {language} if needed.\n\n"
    )
    title_rule = _TITLE_RULE.replace("{language}", language)
    if tool == "lueckentext":
        return base + (
            "Create cloze (gap-filling) exercises. Respond ONLY with a JSON object:\n"
            '{"title": "Short topic title", "exercises": '
            '[{"sentence": "Sentence with ___ as a gap", "answer": "Answer", '
            '"options": ["A", "B", "C", "D"], "correct_idx": 0, '
            '"source_label": "Filename.pdf", "page_number": 5}]}\n'
            + _PERSONAL_RULE + _SOURCE_RULE + title_rule +
            f"Create exactly {count} exercises."
        )
    if tool == "quiz":
        return base + (
            "Create multiple-choice comprehension questions for the given text. "
            "The questions should test understanding of the content.\n\n"
            "Respond ONLY with a JSON object:\n"
            '{"title": "Short topic title", "exercises": '
            '[{"question": "Comprehension question?", "options": ["A", "B", "C", "D"], '
            '"correct_idx": 0, '
            '"source_label": "Filename.pdf", "page_number": 5}]}\n'
            + _PERSONAL_RULE + _SOURCE_RULE + title_rule +
            f"Create exactly {count} questions. Mix easy and hard ones."
        )
    # vokabeltest (default)
    return base + (
        "Create a vocabulary quiz: multiple-choice questions on technical terms from the source text.\n\n"
        "First identify the most important technical terms in the text, then create questions for them.\n"
        "Mix question types:\n"
        "- What does the term X mean?\n"
        "- What is the English translation of X (or German translation)?\n"
        "- Which technical term describes the following: [definition]?\n\n"
        "Pick terms suitable for multiple choice "
        "(clear definition, plausible distractors possible).\n\n"
        "Respond ONLY with a JSON object:\n"
        '{"title": "Short topic title", "exercises": '
        '[{"question": "Question about the technical term?", "options": ["A", "B", "C", "D"], '
        '"correct_idx": 0, '
        '"source_label": "Filename.pdf", "page_number": 5}]}\n'
        + _PERSONAL_RULE + _SOURCE_RULE + title_rule +
        f"Create exactly {count} questions."
    )


def _build_lueckentext_items(exercises: list[dict]) -> tuple[list[dict], list[str]]:
    """Cloze items + the claim text (filled sentence) attributed back to the source."""
    items, claims = [], []
    for ex in exercises:
        items.append({
            "front": ex["sentence"],
            "back": ex["answer"],
            "options": ex["options"],
            "correct_idx": ex["correct_idx"],
        })
        claims.append(f'{ex["sentence"]} {ex["answer"]}'.strip())
    return items, claims


def _build_quiz_items(exercises: list[dict]) -> tuple[list[dict], list[str]]:
    """Quiz/vocab items + the claim text (question + correct answer) for attribution."""
    items, claims = [], []
    for q in exercises:
        answer = q["options"][q["correct_idx"]]
        items.append({
            "front": q["question"],
            "back": answer,
            "options": q["options"],
            "correct_idx": q["correct_idx"],
        })
        claims.append(f'{q["question"]} {answer}'.strip())
    return items, claims
