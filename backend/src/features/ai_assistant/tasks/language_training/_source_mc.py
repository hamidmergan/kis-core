"""Quiz aus Quelltext (mode='source').

Das Quiz stellt zwei Fragearten in einem Satz: Verständnisfragen und Lückensätze,
beide mit Auswahloptionen. Das eigenständige Lückentext-Werkzeug ist deshalb
entfallen, es war dieselbe Aufgabe unter einem eigenen Namen und stand zudem im
Sprachbereich, obwohl die Lücke ein Fachbegriff ist und kein Grammatikthema.
"""

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
    count: int,
    locale: str = "de",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
) -> tuple[list[dict], str]:
    language = _language_label(locale)
    # adaptive_suffix pitches questions/options at the learner's CEFR level; it
    # explicitly must not change the item count, the options or the correct answer.
    tool_prompt = _build_prompt(count, language) + adaptive_suffix + title_avoidance + coverage
    # No "already exists, avoid these" block: feeding the old questions back made the model
    # COPY them verbatim (it even reproduced a "laut Seite 7" question for a page no longer in
    # context). Variation comes instead from the rotating page subset in build_source_context.
    # The TITLE is the exception (title_avoidance): one short string, no few-shot pull.
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

    items, claims = _build_items(exercises)

    # Post-hoc attribution (same pgvector gate as chat): each item cites where its
    # answer actually appears, nav-only, no highlight. The LLM's source_label/page_number
    # (asked for above) are intentionally ignored — attribution decides the real page.
    # multi=False: an MC answer has a single origin, not "every page with the word".
    attach_chips(items, claims, ctx, multi=False)

    title = json_title or title_from_items(client, model, items, ctx.multi_label)
    return items, title


def _build_prompt(count: int, language: str) -> str:
    base = (
        f"You create exercises based on the given source text. "
        f"Write ALL questions, sentences, options, and answers in {language}, "
        f"regardless of the source-text language. Translate source content into {language} if needed.\n\n"
    )
    title_rule = _TITLE_RULE.replace("{language}", language)
    return base + (
        "Create multiple-choice exercises for the given text. Use BOTH kinds, roughly "
        "half and half:\n"
        "- a comprehension question that tests understanding of the content;\n"
        "- a gap sentence: a statement from the text with one key term replaced by ___.\n\n"
        "Respond ONLY with a JSON object. A comprehension item uses \"question\", a gap "
        "item uses \"sentence\" with ___ in it. Everything else is identical:\n"
        '{"title": "Short topic title", "exercises": ['
        '{"question": "Comprehension question?", "options": ["A", "B", "C", "D"], '
        '"correct_idx": 0, "source_label": "Filename.pdf", "page_number": 5}, '
        '{"sentence": "Statement with ___ as a gap.", "options": ["A", "B", "C", "D"], '
        '"correct_idx": 2, "source_label": "Filename.pdf", "page_number": 7}]}\n'
        + _PERSONAL_RULE + _SOURCE_RULE + title_rule +
        f"Create exactly {count} exercises. Mix easy and hard ones."
    )


def _build_items(exercises: list[dict]) -> tuple[list[dict], list[str]]:
    """Item rows + the claim text used for source attribution.

    Both kinds share one shape. A gap item carries "sentence", a comprehension item
    carries "question"; either way the prompt side lands in ``front`` and the correct
    option in ``back``. The UI tells them apart by the gap marker in ``front``, not by
    a separate tool.
    """
    items, claims = [], []
    for ex in exercises:
        prompt_text = (ex.get("question") or ex.get("sentence") or "").strip()
        options = ex.get("options") or []
        idx = ex.get("correct_idx")
        if not prompt_text or not options or idx is None or not (0 <= idx < len(options)):
            continue
        answer = options[idx]
        items.append({
            "front": prompt_text,
            "back": answer,
            "options": options,
            "correct_idx": idx,
            # Which numbered context section the model says it used. Not persisted
            # (finalize_exercise_set only reads known keys), it exists so the caller can
            # check that every section was actually served.
            "_section": ex.get("section"),
        })
        claims.append(f"{prompt_text} {answer}".strip())
    return items, claims
