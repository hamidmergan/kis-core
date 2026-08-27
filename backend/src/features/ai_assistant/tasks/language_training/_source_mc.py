"""Quiz from source text with three exercise kinds: question, gap and true/false."""

import json

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.services.aia_grammar_check import normalize
from src.features.ai_assistant.prompts.language_training_prompts import AIA_HINT_RULE

from src.features.ai_assistant.tasks.language_training._attribution import (
    attach_chips,
    attach_chips_cited,
)
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._hint import attach_hint
from src.features.ai_assistant.tasks.language_training._title import title_from_items
from src.services.llm_context_healing import create_with_shrink


_SOURCE_RULE = (
    "- For every question, include source_label and page_number, the source/page the content came from.\n"
)
_PERSONAL_RULE = (
    "IMPORTANT:\n- Do NOT use personal names in questions. Instead of 'laut Prof. X', write 'laut Material' (German) or 'according to the source' (English), matching the output language.\n"
)
# The title comes with the answer, that saves a second call.
_TITLE_RULE = (
    "- title: a short, concrete topic title in {language} (max 6 words), no quotation marks, "
    "never a filename.\n"
)

# A fixed label per language instead of one invented by the model.
_VERDICT_LABELS = {
    "de": ("Richtig", "Falsch"),
    "en": ("True", "False"),
    "fr": ("Vrai", "Faux"),
    "es": ("Verdadero", "Falso"),
    "it": ("Vero", "Falso"),
    "tr": ("Doğru", "Yanlış"),
    "ar": ("صحيح", "خطأ"),
    "ru": ("Верно", "Неверно"),
}

# Two sample exercises, they sit behind the material and are barred as exercises.
_EXAMPLE_ITEMS = (
    ("Bei sinkender Temperatur arbeitet die Anlage weniger wirtschaftlich.", True),
    ("Die Leistungszahl steigt, wenn es draußen kälter wird.", False),
)

# Derived from the same sentences so example and ban stay together.
_EXAMPLE_MARKERS = frozenset(normalize(satz) for satz, _ in _EXAMPLE_ITEMS)


def _verdict_labels(locale: str) -> tuple[str, str]:
    """The two labels in the configured language, German otherwise."""
    return _VERDICT_LABELS.get((locale or "").lower()[:2], _VERDICT_LABELS["de"])


# Rules from test construction, otherwise the exercise is solvable without the source.
_TRUE_FALSE_RULES = (
    "\nRULES FOR THE TRUE/FALSE STATEMENTS (a statement that breaks one of these can be "
    "marked right without having read the source):\n"
    "- About half of the statements must be false. Do not follow a pattern.\n"
    "- One statement, one idea. Short and unambiguous.\n"
    "- Never use absolute words (always, never, all, none, nobody) and never use hedges "
    "(usually, mostly, as a rule). Both give the answer away.\n"
    "- No negation inside the statement.\n"
    "- Never copy the source verbatim, always say it in your own words.\n"
    "- Make a statement false by changing exactly one detail: a number, a person, a role, "
    "a time, a direction, or a cause. Never invent something the source does not mention "
    "at all, that is too easy to spot.\n"
    "- True and false statements must be about the same length.\n"
)

# The sample exercises as they sit behind the source material.
_EXAMPLE_BLOCK = (
    "\nTwo examples of the SHAPE of a true/false item. They are about different material,\n"
    "never reuse their wording or their content:\n\n"
    + "\n".join(json.dumps({"statement": satz, "answer": urteil}, ensure_ascii=False)
                for satz, urteil in _EXAMPLE_ITEMS)
    + "\n"
)


def _split_counts(count: int) -> tuple[int, int, int]:
    """How many exercises are ordered per kind, as a counted requirement."""
    base, rest = divmod(count, 3)
    return (base + (1 if rest > 0 else 0),
            base + (1 if rest > 1 else 0),
            base)


def generate_mc_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    locale: str = "de",
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
) -> tuple[list[dict], str]:
    # The level block tunes the questions without changing count or solution.
    tool_prompt = _build_prompt(count, language) + adaptive_suffix + title_avoidance + coverage
    # No block with existing questions, the model would just copy them.
    messages = [
        {"role": "system", "content": tool_prompt},
        {"role": "user", "content": _build_user(ctx, language)},
    ]
    # 0.6 for some word variety, the real variation comes from the context.
    response = create_with_shrink(client, endpoint="quiz", model=model, messages=messages, temperature=0.6)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    data = json.loads(answer)
    # Preferably the title comes along, a bare list works too.
    if isinstance(data, dict):
        exercises = data.get("exercises") or []
        json_title = (data.get("title") or "").strip()
    else:
        exercises = data
        json_title = ""
    exercises = list(exercises)[:count]

    items, claims = _build_items(exercises, locale)

    # Attribution after the fact, every exercise names where its answer sits.
    _attach_by_kind(items, claims, ctx)

    title = json_title or title_from_items(client, model, items, ctx.multi_label)
    return items, title


def _attach_by_kind(items: list[dict], claims: list[str], ctx: QuelleContext) -> None:
    """Two attribution runs, pure search for multiple choice, layered for true/false."""
    tf_items, tf_claims, mc_items, mc_claims = [], [], [], []
    for item, claim in zip(items, claims):
        ziel_items, ziel_claims = ((tf_items, tf_claims) if item.pop("_tf", False)
                                   else (mc_items, mc_claims))
        ziel_items.append(item)
        ziel_claims.append(claim)
    if mc_items:
        # A multiple choice answer has an origin, the attribution decides the page.
        attach_chips(mc_items, mc_claims, ctx, multi=False)
    if tf_items:
        attach_chips_cited(tf_items, tf_claims, ctx)


def _build_prompt(count: int, language: str) -> str:
    n_frage, n_luecke, n_tf = _split_counts(count)
    base = (
        f"You create exercises based on the given source text. "
        f"Write ALL questions, sentences, options, and answers in {language}, "
        f"regardless of the source-text language. Translate source content into {language} if needed.\n\n"
    )
    title_rule = _TITLE_RULE.replace("{language}", language)
    return base + (
        "Create exercises for the given text. There are THREE kinds:\n"
        "- a comprehension question that tests understanding of the content, with four "
        "options;\n"
        "- a gap sentence: a statement from the text with one key term replaced by ___, "
        "with four options;\n"
        "- a true/false statement about the content, with no options at all.\n\n"
        "Respond ONLY with a JSON object. A comprehension item uses \"question\", a gap "
        "item uses \"sentence\", both with \"options\" and \"correct_idx\". A true/false "
        "item uses \"statement\" plus \"answer\", which is JSON true or false and nothing "
        "else, and it never carries options. EVERY item carries a \"tip\":\n"
        '{"title": "Short topic title", "exercises": ['
        '{"question": "Comprehension question?", "options": ["A", "B", "C", "D"], '
        '"correct_idx": 0, "tip": "A nudge that does not give it away.", '
        '"source_label": "Filename.pdf", "page_number": 5}, '
        '{"sentence": "Statement with ___ as a gap.", "options": ["A", "B", "C", "D"], '
        '"correct_idx": 2, "tip": "A nudge that does not give it away.", '
        '"source_label": "Filename.pdf", "page_number": 7}, '
        '{"statement": "A claim about the content.", "answer": false, '
        '"tip": "A nudge that does not give it away.", '
        '"source_label": "Filename.pdf", "page_number": 9}]}\n'
        + _TRUE_FALSE_RULES
        + _PERSONAL_RULE + _SOURCE_RULE + title_rule
        + AIA_HINT_RULE.replace("{language}", language) +
        f"Create exactly {n_frage} comprehension questions, {n_luecke} gap sentences and "
        f"{n_tf} true/false statements, {count} exercises in total. Mix easy and hard ones."
    )


def _build_user(ctx: QuelleContext, language: str) -> str:
    """Source material first, sample exercises behind it, otherwise they get copied."""
    return (f"Write the output in {language}.\n\nSources:\n\n{ctx.context}\n\n"
            f"{_EXAMPLE_BLOCK}")


def _build_items(exercises: list[dict], locale: str) -> tuple[list[dict], list[str]]:
    """The exercise rows plus the search text for the source chips."""
    items, claims = [], []
    for ex in exercises:
        if ex.get("statement") is not None or "answer" in ex:
            gebaut = _true_false_item(ex, locale)
        else:
            gebaut = _choice_item(ex)
        if gebaut is None:
            continue
        item, claim = gebaut
        # One place for all three kinds, the hint hangs on the exercise.
        attach_hint(item, ex)
        items.append(item)
        claims.append(claim)
    return items, claims


def _choice_item(ex: dict) -> tuple[dict, str] | None:
    """Comprehension question or gapped sentence, both with four options."""
    prompt_text = (ex.get("question") or ex.get("sentence") or "").strip()
    options = ex.get("options") or []
    idx = ex.get("correct_idx")
    if not prompt_text or not options or idx is None or not (0 <= idx < len(options)):
        return None
    answer = options[idx]
    return {
        "front": prompt_text,
        "back": answer,
        "options": options,
        "correct_idx": idx,
        # Which section the model claims to have used, only for the coverage check.
        "_section": ex.get("section"),
    }, f"{prompt_text} {answer}".strip()


def _true_false_item(ex: dict, locale: str) -> tuple[dict, str] | None:
    """A statement about the source with two options, None otherwise."""
    statement = (ex.get("statement") or "").strip()
    verdict = ex.get("answer")
    options = ex.get("options") or []
    if not statement or not isinstance(verdict, bool) or (options and len(options) != 2):
        return None
    if normalize(statement) in _EXAMPLE_MARKERS:
        return None

    yes, no = _verdict_labels(locale)
    return {
        "front": statement,
        "back": yes if verdict else no,
        "options": [yes, no],
        "correct_idx": 0 if verdict else 1,
        "_section": ex.get("section"),
        # Marks the exercise kind for the attribution, which removes it again.
        "_tf": True,
        # Where the model claims to have taken the exercise from, checked and then removed.
        "_source_label": (ex.get("source_label") or "").strip(),
        "_page": ex.get("page_number"),
    # The search runs on the statement alone, the fixed label would dilute it.
    }, statement
