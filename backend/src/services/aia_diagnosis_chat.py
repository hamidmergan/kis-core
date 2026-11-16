"""Assessment as a short chat, everything didactic lives in the admin prompt."""

import json
import random

from src.services.aia_diagnosis_texts import (  # noqa: F401 - the old import path stays
    CHOICE_TYPE,
    DEFAULT_DIAGNOSIS_PROMPT,
    DEFAULT_GERMAN_QUESTION_PLAN,
    DEFAULT_GRADING_RULES,
    DEFAULT_LEVEL_EXAMPLES,
    FINAL_INSTRUCTION,
    FORCE_FINISH_MESSAGE,
    FREE_TEXT_TYPE,
    REPAIR_MESSAGE,
    _LEGACY_GRADING_RULES,
)
from src.services.aia_level_ladder import LEVELS, build_levels_block


PROMPT_PLACEHOLDER = "{language}"

# The six levels, the whole ladder from A1 to C2.
VALID_LEVELS = set(LEVELS)

# Two exercise kinds: choice graded in code, free text typed.
VALID_QUESTION_TYPES = {CHOICE_TYPE, FREE_TEXT_TYPE}

# The six old names stay readable so stored plans keep working.
LEGACY_TYPE_ALIASES = {
    "multiple choice": CHOICE_TYPE,
    "reading comprehension": CHOICE_TYPE,
    "situation": CHOICE_TYPE,
    "gap fill": FREE_TEXT_TYPE,
    "error correction": FREE_TEXT_TYPE,
    "free writing": FREE_TEXT_TYPE,
}

# This many AI-judged free texts every plan has to carry.
MIN_FREE_TEXT_QUESTIONS = 2
# Limits for a set of answer options.
MIN_OPTIONS = 2
MAX_OPTIONS = 8
# Limits for the answer key of a free text.
MAX_ANSWERS = 8
# Up to this length an answer counts as a word and gets a single-line field.
SHORT_ANSWER_MAX_CHARS = 40
# Limits for the history the browser sends back every round.
MAX_HISTORY_MESSAGES = 40
MAX_MESSAGE_CHARS = 2000
# Ceiling for the prompt edited in the admin area.
MAX_PROMPT_CHARS = 20000

# Admin keys, an empty value always means 'take the default'.
QUESTION_PLAN_SETTING = "language_diagnosis_question_plan_de"
ADAPTIVE_BEHAVIOR_SETTING = "language_diagnosis_adaptive_behavior_de"
ANSWER_MAX_CHARS_SETTING = "language_diagnosis_answer_max_chars_de"
GRADING_RULES_SETTING = "language_diagnosis_grading_rules_de"
LEVEL_EXAMPLES_SETTING = "language_diagnosis_level_examples_de"

# The three visible placeholders in the prompt, missing blocks are appended.
GRADING_PLACEHOLDER = "{grading}"
LEVELS_PLACEHOLDER = "{levels}"
EXAMPLES_PLACEHOLDER = "{examples}"

# One example sentence per level, order and size come from the level ladder.
EXAMPLE_LEVELS = list(LEVELS)

# Soft answer length for the display, the hard limit stays on the server.
DEFAULT_ANSWER_MAX_CHARS = MAX_MESSAGE_CHARS


def canonical_type(raw_type) -> str | None:
    """The exercise kind in its current form, old names are renamed."""
    if not isinstance(raw_type, str):
        return None
    if raw_type in VALID_QUESTION_TYPES:
        return raw_type
    return LEGACY_TYPE_ALIASES.get(raw_type)


def _parse_options(raw_options) -> list[dict] | None:
    """Validates a set of answer options, or None when it is unusable."""
    if not isinstance(raw_options, list) or not (MIN_OPTIONS <= len(raw_options) <= MAX_OPTIONS):
        return None
    cleaned: list[dict] = []
    has_correct = False
    for opt in raw_options:
        if not isinstance(opt, dict):
            return None
        text = opt.get("text")
        if not isinstance(text, str) or not text.strip():
            return None
        # Only a real boolean counts, a 1 is rejected.
        correct = opt.get("correct")
        if not isinstance(correct, bool):
            return None
        has_correct = has_correct or correct
        cleaned.append({"text": text.strip(), "correct": correct})
    return cleaned if has_correct else None


def _parse_answers(raw_answers) -> list[str] | None:
    """Validates the answer key of a free-text question, or None."""
    if not isinstance(raw_answers, list) or not (1 <= len(raw_answers) <= MAX_ANSWERS):
        return None
    cleaned: list[str] = []
    for answer in raw_answers:
        if not isinstance(answer, str) or not answer.strip():
            return None
        cleaned.append(answer.strip())
    return cleaned


def _legacy_answers_from_options(raw_options) -> list[str] | None:
    """Gets the answer key out of the options of an old cloze."""
    cleaned = _parse_options(raw_options)
    if cleaned is None:
        return None
    return [opt["text"] for opt in cleaned if opt["correct"]]


def _parse_step(item) -> dict | None:
    """A stored row in its validated form, or None when unusable."""
    if not isinstance(item, dict):
        return None
    raw_type = item.get("type")
    qtype = canonical_type(raw_type)
    if qtype is None:
        return None
    step = {"type": qtype}
    text = item.get("text")
    if isinstance(text, str) and text.strip():
        step["text"] = text.strip()
    if qtype == CHOICE_TYPE and item.get("options") is not None:
        options = _parse_options(item.get("options"))
        if options is None:
            return None
        step["options"] = options
    if qtype == FREE_TEXT_TYPE:
        answers = None
        if item.get("answers") is not None:
            answers = _parse_answers(item.get("answers"))
            if answers is None:
                return None
        elif raw_type == "gap fill" and item.get("options") is not None:
            answers = _legacy_answers_from_options(item.get("options"))
            if answers is None:
                return None
        if answers:
            step["answers"] = answers
    return step


def step_is_complete(step: dict) -> bool:
    """True when the row carries the test on its own."""
    if not (step.get("text") or "").strip():
        return False
    if step.get("type") == CHOICE_TYPE and not step.get("options"):
        return False
    return True


def parse_question_plan(raw: str) -> list[dict]:
    """The stored question plan, otherwise the shipped default."""
    if not raw or not raw.strip():
        return DEFAULT_GERMAN_QUESTION_PLAN
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return DEFAULT_GERMAN_QUESTION_PLAN
    if not isinstance(data, list) or not data:
        return DEFAULT_GERMAN_QUESTION_PLAN
    plan: list[dict] = []
    for item in data:
        step = _parse_step(item)
        if step is None or not step_is_complete(step):
            return DEFAULT_GERMAN_QUESTION_PLAN
        plan.append(step)
    return plan


def question_plan_is_valid(raw: str) -> bool:
    """True when every row of the admin JSON is well formed."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, list) or not data:
        return False
    for item in data:
        if not isinstance(item, dict):
            return False
        if canonical_type(item.get("type")) is None:
            return False
        if item.get("text") is not None and not isinstance(item.get("text"), str):
            return False
        if _parse_step(item) is None:
            return False
    return True


def count_judged_questions(plan: list[dict]) -> int:
    """How many rows of a plan the AI judges, that is free text without a key."""
    return sum(
        1 for step in plan
        if step.get("type") == FREE_TEXT_TYPE and not step.get("answers")
    )


def question_plan_has_enough_free_text(raw: str) -> bool:
    """True when enough AI-judged questions are in the plan."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, list):
        return False
    steps = [step for step in (_parse_step(item) for item in data) if step is not None]
    return count_judged_questions(steps) >= MIN_FREE_TEXT_QUESTIONS


def first_incomplete_question(raw: str) -> int | None:
    """The number of the first unfinished row, None otherwise."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    for number, item in enumerate(data, 1):
        step = _parse_step(item)
        if step is None or not step_is_complete(step):
            return number
    return None


def correct_values(step: dict) -> set[str]:
    """The set of option texts marked correct on an authored option question."""
    return {opt["text"].strip() for opt in step.get("options", []) if opt.get("correct")}


def option_values(step: dict) -> list[str]:
    """The option texts without the answer markers, the key stays on the server."""
    return [opt["text"] for opt in step.get("options", [])]


def is_multi_correct(step: dict) -> bool:
    """True when more than one option is correct (checkbox, not radio)."""
    return len(correct_values(step)) > 1


def grade_selection(step: dict, selected: list[str]) -> bool:
    """Grades a choice question in code, correct only on exactly the right set."""
    correct = correct_values(step)
    if not correct:
        return False
    picked = {s.strip() for s in selected}
    return picked == correct


def answer_key(step: dict) -> list[str]:
    """The accepted answers of a free text, they never go to the browser."""
    return list(step.get("answers", []))


# Punctuation at the end of a typed answer is a habit, not a mistake.
_TRAILING_PUNCTUATION = ".,;:!?…"


def normalize_typed_answer(value: str) -> str:
    """Folds a typed answer down to what carries meaning."""
    folded = " ".join(value.split()).rstrip(_TRAILING_PUNCTUATION).strip()
    return folded.lower()


def grade_typed(step: dict, answer: str) -> bool:
    """Grades a free text with a key in code, a near miss is wrong."""
    key = {normalize_typed_answer(a) for a in answer_key(step)}
    if not key:
        return False
    return normalize_typed_answer(answer) in key


def question_mode(step: dict) -> str:
    """How a row is delivered and graded, the key decides."""
    if step.get("type") == CHOICE_TYPE:
        return "manual_options"
    if step.get("answers"):
        return "manual_typed"
    return "manual_text"


def _shuffle(values: list[str], rng=None) -> list[str]:
    """A shuffled copy, the display order reveals nothing."""
    order = list(values)
    (rng or random).shuffle(order)
    return order


def wants_short_box(step: dict) -> bool:
    """True when the learner gets a single-line field here."""
    answers = answer_key(step)
    return bool(answers) and all(len(a) <= SHORT_ANSWER_MAX_CHARS for a in answers)


def manual_question_payload(step: dict, rng=None) -> dict:
    """The delivery of a hand-written question, without a model."""
    payload = {"done": False, "message": step["text"]}
    if step.get("type") == CHOICE_TYPE and step.get("options"):
        payload["options"] = _shuffle(option_values(step), rng)
        payload["multi"] = is_multi_correct(step)
    if wants_short_box(step):
        payload["short"] = True
    return payload


def answered_items(history: list[dict]) -> list[dict]:
    """Pairs every asked question with the learner's answer."""
    items: list[dict] = []
    pending: dict | None = None
    for turn in history:
        if turn.get("role") == "assistant":
            pending = turn
        elif turn.get("role") == "user":
            q = pending or {}
            items.append({
                "question": (q.get("content") or "").strip(),
                "options": q.get("options") or [],
                "selected": turn.get("selected"),
                "answer": (turn.get("content") or "").strip(),
            })
            pending = None
    return items


def is_empty_run(history: list[dict]) -> bool:
    """True when the learner supplied nothing at all."""
    items = answered_items(history)
    return bool(items) and all(
        not item["answer"] and not item["selected"] for item in items
    )


def build_grading_brief(plan: list[dict], history: list[dict]) -> str:
    """The record the one final call grades from."""
    lines: list[str] = []
    for i, item in enumerate(answered_items(history)):
        step = plan[i] if i < len(plan) else {"type": "?"}
        qtype = step.get("type", "?")
        mode = question_mode(step)
        header = f"Question {i + 1} ({qtype})"
        q_text = (step.get("text") or item["question"] or "").strip()
        selected, answer = item["selected"], item["answer"]

        if mode == "manual_options":
            opts, correct = option_values(step), sorted(correct_values(step))
            if selected is not None:
                verdict = "CORRECT" if grade_selection(step, selected) else "INCORRECT"
                lines.append(
                    f"{header}: authored choice. Question: {q_text} Options: {opts}. "
                    f"Correct answer(s): {correct}. Learner selected: {list(selected)}. "
                    f"RESULT (already graded in code, use exactly this): {verdict}."
                )
            else:
                lines.append(
                    f"{header}: authored choice. Question: {q_text} Options: {opts}. "
                    f"Correct answer(s): {correct}. Learner wrote in free words: \"{answer}\". "
                    "Decide which option they meant, then whether it is correct."
                )
        elif mode == "manual_typed":
            verdict = "CORRECT" if grade_typed(step, answer) else "INCORRECT"
            lines.append(
                f"{header}: authored free text with a solution key, the learner types. "
                f"Question: {q_text} Accepted answer(s): {answer_key(step)}. "
                f"Learner typed: \"{answer}\". "
                f"RESULT (already graded in code, use exactly this): {verdict}."
            )
        else:  # manual_text
            lines.append(
                f"{header}: authored free-text task. Question: {q_text} "
                f"Learner answered: \"{answer}\". Judge the answer for its language level."
            )
    return "\n\n".join(lines)


def build_final_messages(system_prompt: str, plan: list[dict], history: list[dict]) -> list[dict]:
    """The messages for the one grading call."""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": FINAL_INSTRUCTION + "\n\n" + build_grading_brief(plan, history)},
    ]


class DiagnosisChatError(ValueError):
    """Raised when the model's turn is unparseable or fails validation."""


def parse_level_examples(raw: str) -> dict:
    """Reads the examples per level, missing ones stay on the default."""
    examples = dict(DEFAULT_LEVEL_EXAMPLES)
    if not raw or not raw.strip():
        return examples
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return examples
    if not isinstance(data, dict):
        return examples
    for level in EXAMPLE_LEVELS:
        value = data.get(level)
        if isinstance(value, str) and value.strip():
            examples[level] = value.strip()
    return examples


def example_items(raw: str) -> list[str]:
    """Splits a level's example value into single examples."""
    normalized = (raw or "").replace("--", "\n")
    return [ln.strip() for ln in normalized.splitlines() if ln.strip()]


def build_examples_block(examples: dict) -> str:
    """Renders the examples per level as a bullet list."""
    lines: list[str] = []
    for level in EXAMPLE_LEVELS:
        items = example_items(examples.get(level, ""))
        if not items:
            continue
        if len(items) == 1:
            lines.append(f"- {level}: {items[0]}")
        else:
            lines.append(f"- {level}:")
            lines.extend(f"  - {item}" for item in items)
    return "\n".join(lines)


def render_system_prompt(template: str, language_name: str) -> str:
    """Substitute the target language into the admin-managed prompt template."""
    return template.replace(PROMPT_PLACEHOLDER, language_name)


def assemble_system_prompt(
    main_prompt: str,
    grading_rules: str,
    descriptions: dict,
    examples: dict,
    language_name: str,
) -> str:
    """Builds the full assessment prompt from its three blocks."""
    text = main_prompt
    if GRADING_PLACEHOLDER in text:
        text = text.replace(GRADING_PLACEHOLDER, grading_rules.strip())
    else:
        text = text.rstrip() + "\n\nLEVEL ASSIGNMENT\n" + grading_rules.strip()
    levels = build_levels_block(descriptions)
    if LEVELS_PLACEHOLDER in text:
        text = text.replace(LEVELS_PLACEHOLDER, levels)
    else:
        text = (
            text.rstrip()
            + "\n\nThese describe a typical learner at each outcome:\n"
            + levels
        )
    block = build_examples_block(examples)
    if EXAMPLES_PLACEHOLDER in text:
        text = text.replace(EXAMPLES_PLACEHOLDER, block)
    else:
        text = text.rstrip() + "\n\nCALIBRATION EXAMPLES\n" + block
    return render_system_prompt(text, language_name)


def _strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        # A fence on one line has no first line to drop, the JSON search behind copes with it.
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return text


def _loads_lenient(raw: str):
    """Reads the model answer even when prose surrounds the JSON."""
    text = _strip_fence(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise DiagnosisChatError("Response contains no JSON object")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise DiagnosisChatError(f"Response is not valid JSON: {exc}") from exc


def parse_turn_response(raw: str) -> dict:
    """Validates a model answer, surplus fields are dropped."""
    parsed = _loads_lenient(raw)

    if not isinstance(parsed, dict):
        raise DiagnosisChatError("Response must be a JSON object")

    message = parsed.get("message")
    if not isinstance(message, str) or not message.strip():
        raise DiagnosisChatError("Missing or empty message")

    if not parsed.get("done"):
        return {"done": False, "message": message.strip()}

    level = parsed.get("level")
    if level not in VALID_LEVELS:
        raise DiagnosisChatError(f"Invalid level: {level!r}")

    return {
        "done": True,
        "message": message.strip(),
        "level": level,
    }
