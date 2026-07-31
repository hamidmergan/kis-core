"""Language diagnosis as a short adaptive chat interview.

The learner's CEFR level used to come from a fixed 12-question form whose items
were hardcoded in one language. This module replaces that with a chat: the
model asks one question at a time, adapts to the answers, and closes with a
verdict. Everything didactic lives in the prompt, which an admin edits centrally
(setting ``language_diagnosis_prompt``), so a language expert can change the
method without a code change.

The prompt is language-agnostic. It carries the CEFR anchors, which are the same
scale for every language, and takes the actual target language through the
``{language}`` placeholder. That is why there is ONE prompt rather than one per
language.

Substitution is a plain ``str.replace``, never ``str.format``: the template
contains a JSON example full of braces, and it is free text an admin types.
"""

import json
import random


PROMPT_PLACEHOLDER = "{language}"

# The six CEFR outcomes. The test used to collapse everything above B1 into a
# single "B1+", on the theory that a learner past B1 needs no support. The scale
# now runs the full ladder A1..C2 so the adaptive chat can pitch a B2, C1 or C2
# learner as precisely as an A1 one. Telling C1 from C2 is the least reliable
# split and needs its own C1/C2 questions in the plan; the admin owns the plan,
# so how deep the test really reaches is the expert's choice, not a code limit.
VALID_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}

# Fixed-length test. Every learner answers the same questions, so two results are
# comparable and the UI can show "question 3 of 12". A question carries only a
# TASK TYPE, never a CEFR level: the expert does not label a question's level, the
# model reads the learner's answers and places them A1..C2 holistically, measured
# against the CALIBRATION EXAMPLES. The difficulty spread comes from POSITION, not
# a per-question band: the test rises from very easy (first slots) to very
# demanding (last), so the model varies difficulty by where a slot sits. The six
# task types spread across the slots; the plan keeps at least
# MIN_FREE_TEXT_QUESTIONS free-text slots, since free text is what the level
# actually rests on. The admin owns the plan. Index 0 is Q1.
QUESTION_PLAN = [
    {"type": "gap fill"},
    {"type": "multiple choice"},
    {"type": "error correction"},
    {"type": "multiple choice"},
    {"type": "reading comprehension"},
    {"type": "situation"},
    {"type": "multiple choice"},
    {"type": "free writing"},
    {"type": "reading comprehension"},
    {"type": "error correction"},
    {"type": "free writing"},
    {"type": "multiple choice"},
]
QUESTION_COUNT = len(QUESTION_PLAN)

# Task types that present labelled options a), b), c), d). For these the backend
# dictates WHERE the correct option sits, picking a RANDOM position each time.
# Models have a strong bias to put the answer at a), which makes the test feel
# broken ("the answer is always a"); a fixed rotation fixed that but was itself
# predictable (a learner could pick by position without reading), so the position
# is now drawn at random. Error correction and free writing have no options and
# are skipped.
OPTION_QUESTION_TYPES = {
    "gap fill",
    "multiple choice",
    "reading comprehension",
    "situation",
}
# The two task types that never carry options: the learner writes their own
# answer, which only the final LLM call can judge.
FREE_TEXT_QUESTION_TYPES = {"error correction", "free writing"}
# Every plan must carry at least this many free-text questions. Multiple choice
# only shows what a learner RECOGNISES; free text is the only production the model
# can judge for range, complexity and register, and it is what a level above B1
# has to rest on. Without this floor an all-multiple-choice plan would let the
# model hand out C1/C2 on recognition alone. Two gives a second signal without
# overloading a weak learner (who can still skip), and the shipped plans carry
# four, so the default is never affected.
MIN_FREE_TEXT_QUESTIONS = 2
# Bounds for an authored option set. Four is the shipped shape, but an expert may
# use fewer or a couple more; a single option is not a choice and a runaway count
# is a paste accident.
MIN_OPTIONS = 2
MAX_OPTIONS = 8
CORRECT_OPTION_POSITIONS = ["a", "b", "c", "d"]
# History caps. The client keeps the transcript and posts it back each turn, so
# these bound how big a single request may grow.
MAX_HISTORY_MESSAGES = 40
MAX_MESSAGE_CHARS = 2000
# Ceiling for the admin-edited prompt, so a paste accident cannot blow up every
# diagnosis request.
MAX_PROMPT_CHARS = 20000

# Admin-settings keys (German-scoped, "_de" suffix). An empty stored value always
# means "use the code default", so the diagnosis can never end up without a plan.
QUESTION_PLAN_SETTING = "language_diagnosis_question_plan_de"
ADAPTIVE_BEHAVIOR_SETTING = "language_diagnosis_adaptive_behavior_de"
ANSWER_MAX_CHARS_SETTING = "language_diagnosis_answer_max_chars_de"
GRADING_RULES_SETTING = "language_diagnosis_grading_rules_de"
LEVEL_EXAMPLES_SETTING = "language_diagnosis_level_examples_de"

# Placeholders inside the main prompt. {grading} is filled with the grading rules
# (the Einstufungs-Regeln field), {examples} with the per-band calibration example
# list. Both are VISIBLE in the prompt itself, so nothing is merged in secretly.
# If a custom prompt drops a placeholder, that block is appended at the end.
GRADING_PLACEHOLDER = "{grading}"
EXAMPLES_PLACEHOLDER = "{examples}"

# The bands that carry a calibration example, one per CEFR level. Each is a
# reference answer the final grading call compares free-text answers against, and
# the adaptive chat reuses the same samples to calibrate how it writes per level.
EXAMPLE_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Soft UI limit for the answer length. The hard backend cap stays
# MAX_MESSAGE_CHARS; this one only drives the counter and maxlength in the client.
DEFAULT_ANSWER_MAX_CHARS = MAX_MESSAGE_CHARS

VALID_QUESTION_TYPES = {
    "gap fill",
    "multiple choice",
    "error correction",
    "reading comprehension",
    "situation",
    "free writing",
}


def _parse_options(raw_options) -> list[dict] | None:
    """Validate an authored option set, or None when it is unusable.

    Each option is ``{"text": <non-empty>, "correct": <bool>}``. A usable set has
    MIN_OPTIONS..MAX_OPTIONS options and at least one correct one (the expert may
    mark several correct; the model path enforces exactly one separately). Returns
    the cleaned options, or None so the caller can revert the whole plan. Text is
    stripped; the correct flag is coerced to a plain bool.
    """
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
        # bool is an int subclass; accept only a real boolean so a stray 1/0 that
        # would silently read as correct is rejected rather than guessed.
        correct = opt.get("correct")
        if not isinstance(correct, bool):
            return None
        has_correct = has_correct or correct
        cleaned.append({"text": text.strip(), "correct": correct})
    return cleaned if has_correct else None


def parse_question_plan(raw: str) -> list[dict]:
    """Parse the admin question-plan JSON, falling back to the shipped default.

    Each item is ``{"type": <one of VALID_QUESTION_TYPES>}``. A question carries no
    CEFR level: the model places the learner from their answers, not from a label
    on the question. Optional authoring fields:
      * ``"text"``   the verbatim question shown to the learner.
      * ``"options"`` (option types only) the answer options, each with a
        ``correct`` flag. Graded in code, so no model call. A structurally broken
        option set reverts the whole plan to the default (existing philosophy:
        always run on a usable plan).
    A legacy ``"band"`` field from older plans, an ``"example"`` and options on a
    free-text type are all ignored rather than rejected, so an old or stray field
    is forgiving.
    """
    if not raw or not raw.strip():
        return QUESTION_PLAN
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return QUESTION_PLAN
    if not isinstance(data, list) or not data:
        return QUESTION_PLAN
    plan: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            return QUESTION_PLAN
        qtype = item.get("type")
        if qtype not in VALID_QUESTION_TYPES:
            return QUESTION_PLAN
        step = {"type": qtype}
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            step["text"] = text.strip()
        if qtype in OPTION_QUESTION_TYPES and item.get("options") is not None:
            options = _parse_options(item.get("options"))
            if options is None:
                return QUESTION_PLAN
            step["options"] = options
        plan.append(step)
    return plan


# Shipped German question set. Unlike QUESTION_PLAN (type only, one prompt for
# every language), these are fully authored: real German text and options with a
# correct flag. A German diagnosis with no admin config uses this, so the common
# case runs instantly with ZERO model calls. Any OTHER language falls back to
# QUESTION_PLAN and the model generates the items, so the test stays
# language-agnostic out of the box. The admin can edit or replace all of it. The
# questions are ordered from very easy to very demanding, so the test spans the
# whole range; the model reads the answers to place the learner, the questions
# carry no level themselves. Each option item has exactly one correct option and
# every distractor a real, gradeable mistake.
GERMAN_LANGUAGE_CODE = "de"
DEFAULT_GERMAN_QUESTION_PLAN = [
    {
        "type": "gap fill",
        "text": "Setze das passende Wort ein.\n\nIch ___ jeden Tag zur Arbeit.",
        "options": [
            {"text": "gehe", "correct": True},
            {"text": "gehst", "correct": False},
            {"text": "geht", "correct": False},
            {"text": "gehen", "correct": False},
        ],
    },
    {
        "type": "multiple choice",
        "text": "Welches Wort passt?\n\n___ Buch liegt auf dem Tisch.",
        "options": [
            {"text": "Das", "correct": True},
            {"text": "Der", "correct": False},
            {"text": "Die", "correct": False},
            {"text": "Den", "correct": False},
        ],
    },
    {
        "type": "error correction",
        "text": "Der Satz hat einen Fehler. Schreibe ihn richtig.\n\nGestern ich habe einen Film gesehen.",
    },
    {
        "type": "multiple choice",
        "text": "Welches Wort passt?\n\nIch fahre mit ___ Bus zur Uni.",
        "options": [
            {"text": "dem", "correct": True},
            {"text": "den", "correct": False},
            {"text": "das", "correct": False},
            {"text": "der", "correct": False},
        ],
    },
    {
        "type": "reading comprehension",
        "text": ("Lies den Satz und beantworte die Frage.\n\n"
                 "Weil der Zug Verspätung hatte, kam Anna zu spät zur Besprechung.\n\n"
                 "Warum kam Anna zu spät?"),
        "options": [
            {"text": "Der Zug war nicht pünktlich.", "correct": True},
            {"text": "Anna ist zu spät aufgestanden.", "correct": False},
            {"text": "Die Besprechung hat früher angefangen.", "correct": False},
            {"text": "Anna hat den Zug verpasst.", "correct": False},
        ],
    },
    {
        "type": "situation",
        "text": ("Was sagst du in dieser Situation?\n\n"
                 "Du kommst zu spät zu einem Termin und möchtest dich höflich entschuldigen."),
        "options": [
            {"text": "Entschuldigen Sie bitte die Verspätung.", "correct": True},
            {"text": "Das ist mir egal.", "correct": False},
            {"text": "Sie sind zu spät.", "correct": False},
            {"text": "Ich habe jetzt keine Zeit.", "correct": False},
        ],
    },
    {
        "type": "multiple choice",
        "text": "Welche Wörter passen in die Lücken?\n\n___ mehr man übt, ___ besser wird man.",
        "options": [
            {"text": "Je … desto", "correct": True},
            {"text": "Wenn … dann", "correct": False},
            {"text": "So … wie", "correct": False},
            {"text": "Umso … je", "correct": False},
        ],
    },
    {
        "type": "free writing",
        "text": ("Schreibe zwei bis drei Sätze.\n\n"
                 "Beschreibe, was du letztes Wochenende gemacht hast."),
    },
    {
        "type": "reading comprehension",
        "text": ("Lies den Satz und beantworte die Frage.\n\n"
                 "Hätte das Unternehmen früher reagiert, wäre der Schaden vermeidbar gewesen.\n\n"
                 "Was ist tatsächlich passiert?"),
        "options": [
            {"text": "Das Unternehmen reagierte zu spät, und der Schaden trat ein.", "correct": True},
            {"text": "Das Unternehmen reagierte früh und verhinderte den Schaden.", "correct": False},
            {"text": "Der Schaden war von Anfang an nicht zu verhindern.", "correct": False},
            {"text": "Das Unternehmen will in Zukunft schneller reagieren.", "correct": False},
        ],
    },
    {
        "type": "error correction",
        "text": ("Der Satz hat einen Fehler. Schreibe ihn richtig.\n\n"
                 "Je länger die Sitzung dauerte, desto ungeduldiger wurden die Teilnehmer, "
                 "trotz sie sich vorgenommen hatten, ruhig zu bleiben."),
    },
    {
        "type": "free writing",
        "text": ("Schreibe drei bis vier Sätze.\n\n"
                 "Nimm Stellung: Sollten Universitäten eine Anwesenheitspflicht in "
                 "Vorlesungen verlangen? Begründe deine Meinung."),
    },
    {
        "type": "multiple choice",
        "text": ("Welches Wort passt stilistisch am besten in diesen gehobenen Satz?\n\n"
                 "Die Kommission hat die Vorwürfe nach eingehender Prüfung ___."),
        "options": [
            {"text": "entkräftet", "correct": True},
            {"text": "kaputtgemacht", "correct": False},
            {"text": "weggemacht", "correct": False},
            {"text": "abgesagt", "correct": False},
        ],
    },
]


def resolve_question_plan(stored_raw: str, language_code: str | None) -> list[dict]:
    """The plan to run: an admin-saved plan wins; otherwise the language decides.

    A non-empty stored plan is always used (it is the admin's explicit choice,
    across all languages). With no stored plan, a German diagnosis gets the
    shipped authored German set (instant, no model calls), and any other language
    gets the language-agnostic ``QUESTION_PLAN`` so the model generates the items.
    """
    if stored_raw and stored_raw.strip():
        return parse_question_plan(stored_raw)
    if language_code == GERMAN_LANGUAGE_CODE:
        return DEFAULT_GERMAN_QUESTION_PLAN
    return QUESTION_PLAN


def question_plan_is_valid(raw: str) -> bool:
    """True iff every item in the admin JSON is well-formed.

    The save path uses this to reject a typo with a 400, rather than storing
    something the runtime then silently reverts to a default. Mirrors
    :func:`parse_question_plan`: the type must be known, an option set (option
    types only) must pass ``_parse_options``, and text must be a string. A legacy
    ``band`` field is ignored.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, list) or not data:
        return False
    for item in data:
        if not isinstance(item, dict):
            return False
        if item.get("type") not in VALID_QUESTION_TYPES:
            return False
        if item.get("text") is not None and not isinstance(item.get("text"), str):
            return False
        if item["type"] in OPTION_QUESTION_TYPES and item.get("options") is not None:
            if _parse_options(item.get("options")) is None:
                return False
    return True


def count_free_text_questions(plan: list[dict]) -> int:
    """How many steps in a parsed plan are free-text (error correction / free writing)."""
    return sum(1 for step in plan if step.get("type") in FREE_TEXT_QUESTION_TYPES)


def question_plan_has_enough_free_text(raw: str) -> bool:
    """True iff the admin plan carries at least MIN_FREE_TEXT_QUESTIONS free-text
    questions.

    Kept separate from :func:`question_plan_is_valid` (which checks structure) on
    purpose: a short, structurally fine plan used in isolation still validates.
    This floor is a save-path policy, enforced by the settings route, so a plan
    the model could grade well cannot be stored without any production to judge.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, list):
        return False
    return count_free_text_questions(
        [item for item in data if isinstance(item, dict)]
    ) >= MIN_FREE_TEXT_QUESTIONS


def correct_values(step: dict) -> set[str]:
    """The set of option texts marked correct on an authored option question."""
    return {opt["text"].strip() for opt in step.get("options", []) if opt.get("correct")}


def option_values(step: dict) -> list[str]:
    """The option texts in authoring order, without the correct flags.

    This is the client-facing shape: the answer key never leaves the server, and
    the display order is shuffled at serve time, so position carries no signal.
    """
    return [opt["text"] for opt in step.get("options", [])]


def is_multi_correct(step: dict) -> bool:
    """True when more than one option is correct (checkbox, not radio)."""
    return len(correct_values(step)) > 1


def grade_selection(step: dict, selected: list[str]) -> bool:
    """Deterministic all-or-nothing grade for an authored option question.

    Correct iff the learner's picks are exactly the correct set: every correct
    option and no wrong one. Matching is exact after stripping whitespace; case
    is significant. Anything that is not a clean pick (free words, a near miss) is
    never graded here, it is left to the final LLM, so the code path never guesses.
    """
    correct = correct_values(step)
    if not correct:
        return False
    picked = {s.strip() for s in selected}
    return picked == correct


def question_mode(step: dict) -> str:
    """How a slot is served and graded: 'manual_options', 'manual_text' or 'auto'.

    * manual_options: an option type with both a question text and an answer key.
      Served instantly, graded in code.
    * manual_text: a free-text type with a question text. Served instantly, judged
      by the final LLM.
    * auto: anything else (bare band/type, or an option type whose answer key is
      not filled in yet). The model generates it, exactly as before.
    """
    qtype = step.get("type")
    has_text = bool((step.get("text") or "").strip())
    if qtype in OPTION_QUESTION_TYPES:
        if has_text and correct_values(step):
            return "manual_options"
        return "auto"
    if qtype in FREE_TEXT_QUESTION_TYPES:
        return "manual_text" if has_text else "auto"
    return "auto"


def validate_auto_options(options: list[dict]) -> list[dict]:
    """Enforce the single-correct rule on a model-generated option set.

    The model must return MIN_OPTIONS..MAX_OPTIONS options with EXACTLY ONE marked
    correct. Two correct is the exact bug the redesign kills (a distractor that is
    itself a valid answer); zero correct is unusable. Raises DiagnosisChatError so
    the turn can be repaired, rather than showing the learner a broken item.
    """
    cleaned = _parse_options(options)
    if cleaned is None:
        raise DiagnosisChatError("Auto question options are structurally invalid")
    correct = sum(1 for opt in cleaned if opt["correct"])
    if correct != 1:
        raise DiagnosisChatError(
            f"Auto question must have exactly one correct option, got {correct}"
        )
    return cleaned


def _shuffle(values: list[str], rng=None) -> list[str]:
    """A shuffled copy of ``values``. Display order carries no signal, so the
    correct answer is never learnable from position. ``rng`` is injectable so a
    test can pin the order."""
    order = list(values)
    (rng or random).shuffle(order)
    return order


def manual_question_payload(step: dict, rng=None) -> dict:
    """Client payload for an expert-authored question, with no model involved.

    The message is the authored question text. Option questions also carry the
    shuffled option values (never the correct flags) and a ``multi`` flag so the
    client picks radio vs checkbox. Free-text questions carry only the message.
    """
    payload = {"done": False, "message": step["text"]}
    if step.get("type") in OPTION_QUESTION_TYPES and step.get("options"):
        payload["options"] = _shuffle(option_values(step), rng)
        payload["multi"] = is_multi_correct(step)
    return payload


def parse_auto_question(raw: str, want_options: bool) -> dict:
    """Validate one model-generated question turn.

    Returns ``{"message": str}`` and, for option types, ``{"options": [...]}`` with
    the correct flags kept for the caller to strip after shuffling. Enforces the
    single-correct rule via ``validate_auto_options`` so a two-correct item is
    repaired, not shown.
    """
    parsed = _loads_lenient(raw)
    if not isinstance(parsed, dict):
        raise DiagnosisChatError("Response must be a JSON object")
    message = parsed.get("message")
    if not isinstance(message, str) or not message.strip():
        raise DiagnosisChatError("Missing or empty message")
    result: dict = {"message": message.strip()}
    if want_options:
        result["options"] = validate_auto_options(parsed.get("options"))
    return result


def auto_question_payload(parsed: dict, rng=None) -> dict:
    """Client payload for a model-generated question, stripped of the answer key.

    The correct flags never leave the server; the options are shuffled to values
    only. Auto questions are always single-correct, so ``multi`` is always False.
    """
    payload = {"done": False, "message": parsed["message"]}
    if "options" in parsed:
        payload["options"] = _shuffle([opt["text"] for opt in parsed["options"]], rng)
        payload["multi"] = False
    return payload


def answered_items(history: list[dict]) -> list[dict]:
    """Pair each asked question with the learner's answer, in order.

    One dict per answered question: the question text shown, the options shown (if
    any), the picks the learner clicked (``selected``, a list or None) and the raw
    text they typed (``answer``). A trailing unanswered assistant turn is ignored.
    """
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
    """True when the learner produced nothing at all: no text and no pick.

    There is then nothing to grade. Asked to place a learner from a record of
    blank answers, the model picks between the lower bands at random and, because
    the prompt asks for an encouraging closing message, invents a strength to
    praise. The caller answers with a fixed A1 instead. An empty transcript is
    NOT an empty run: it is no run, so it returns False.
    """
    items = answered_items(history)
    return bool(items) and all(
        not item["answer"] and not item["selected"] for item in items
    )


def build_grading_brief(plan: list[dict], history: list[dict]) -> str:
    """The record the one final call grades from: every question, its answer key
    where the expert set one, and the learner's answer.

    Authored option answers that arrived as clean picks are graded in code and
    handed to the model as a fixed RESULT it must not second-guess. Everything
    else (free-worded picks, model-generated items, free-text answers) is laid out
    for the model to judge. The answer key for authored questions is included here
    so the model can judge a free-worded answer, and it never travels to the client.
    """
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
        elif mode == "manual_text":
            lines.append(
                f"{header}: authored free-text task. Question: {q_text} "
                f"Learner answered: \"{answer}\". Judge the answer for its language level."
            )
        elif qtype in OPTION_QUESTION_TYPES:  # auto choice
            picked = list(selected) if selected is not None else repr(answer)
            lines.append(
                f"{header}: model-generated choice. Question: {q_text} "
                f"Options shown: {item['options']}. Learner answered: {picked}. "
                "Decide which option they meant, then whether it is correct."
            )
        else:  # auto free-text
            lines.append(
                f"{header}: model-generated free-text task. Question: {q_text} "
                f"Learner answered: \"{answer}\". Judge the answer for its language level."
            )
    return "\n\n".join(lines)


# Sent as the first user turn so the model always sees a user role before it
# speaks. Never shown to the learner.
KICKOFF_MESSAGE = "Begin the interview now with your first question."
# Appended once all questions are answered, to pull the verdict out.
FORCE_FINISH_MESSAGE = (
    "That was the learner's last answer. Do not ask another question. "
    "Reply now with the final JSON object: done=true, message and level."
)
# Injected on every asking turn so the model does not have to count the
# transcript itself: the backend knows the position and dictates the task type.
# There is no per-question CEFR band; difficulty comes from POSITION, so an early
# slot is easy and a late one hard, and the whole test spans very easy to very
# demanding.
NEXT_QUESTION_MESSAGE = (
    "Now ask question {number} of {total}. It must be a {type} task. This test "
    "rises from very easy at the start to very demanding at the end, so choose a "
    "difficulty that fits position {number} of {total}, whatever the learner "
    "answered before. Do not give any verdict yet: reply with done=false and only "
    "this one question."
)
# Used when a slot carries a verbatim question text but no answer key, so the
# model still has to ask it and (for option types) build the options.
NEXT_QUESTION_VERBATIM_MESSAGE = (
    "Now ask question {number} of {total}. Ask EXACTLY this question, word for "
    "word, changing nothing about its wording:\n\n{text}\n\n"
    "Do not give any verdict yet: reply with done=false and only this one question."
)
# Appended for option-bearing questions: the options travel in a structured array
# with a single correct flag, never inside the message, so the interface can
# shuffle them and the answer never has a fixed position.
AUTO_OPTIONS_DIRECTIVE = (
    " This is an option task. Put the answer options in the \"options\" array, "
    "each {\"text\": ..., \"correct\": true|false}, with EXACTLY ONE correct and "
    "every other one a real mistake. Keep the options OUT of \"message\"."
)


def next_question_message(number: int, plan: list[dict] | None = None) -> str:
    """The per-turn instruction that fixes an auto question's number and type.

    ``plan`` defaults to the shipped ``QUESTION_PLAN``. A slot with a verbatim
    ``text`` is asked word for word; otherwise the type is dictated and the
    difficulty follows the slot's position (early easy, late hard). For option
    types the structured-options directive is appended so the model returns the
    options as data, not as a), b), c), d) inside the message.
    """
    steps = plan or QUESTION_PLAN
    step = steps[number - 1]
    total = len(steps)
    if step.get("text"):
        message = NEXT_QUESTION_VERBATIM_MESSAGE.format(
            number=number, total=total, text=step["text"]
        )
    else:
        message = NEXT_QUESTION_MESSAGE.format(
            number=number, total=total, type=step["type"]
        )
    if step["type"] in OPTION_QUESTION_TYPES:
        message += AUTO_OPTIONS_DIRECTIVE
    return message


# The user turn that carries the finished record to the single final grading call.
FINAL_INSTRUCTION = (
    "The learner has answered every question. The full record follows. Apply the "
    "LEVEL ASSIGNMENT rules and reply with ONLY the final JSON object: done=true, "
    "message and level. Where a RESULT is given, use it as it stands."
)


def build_final_messages(system_prompt: str, plan: list[dict], history: list[dict]) -> list[dict]:
    """Messages for the ONE grading call: the system prompt, then the record.

    The record (:func:`build_grading_brief`) carries every question, the answer
    key for authored items and the code-graded results, so the model judges only
    what it must (free text, free-worded picks, model-generated items) and assigns
    the level. It replaces the old per-turn verdict flow entirely.
    """
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": FINAL_INSTRUCTION + "\n\n" + build_grading_brief(plan, history)},
    ]


# Sent after an unparseable turn. Measured against the production model, roughly
# one turn in twelve comes back as the bare question text with no JSON at all.
REPAIR_MESSAGE = (
    "Your last reply was not a JSON object, so it could not be used. Send the "
    "same turn again as ONLY the JSON object from the output format, with no "
    "text before or after it."
)


class DiagnosisChatError(ValueError):
    """Raised when the model's turn is unparseable or fails validation."""


DEFAULT_DIAGNOSIS_PROMPT = """You are a CEFR assessor running a short diagnostic interview with a learner.
The target language is {language}. Conduct the ENTIRE conversation in {language}.

GOAL
Sort the learner into one of the six CEFR levels, A1, A2, B1, B2, C1 or C2. Read
the level off the learner's OWN answers, above all their free-text writing,
measured against the CALIBRATION EXAMPLES below. The questions
carry no level of their own, you decide the level. It then drives how simply the
tutor writes back to the learner, so an accurate placement across the whole
ladder matters, not only telling "needs support" from "does not".

THE TEST RISES FROM EASY TO HARD
You ask a fixed set of questions. The task TYPE of each is fixed, but the
questions carry NO CEFR level. Instead the test as a whole must rise from very
easy at the start to very demanding at the end, so make an early question simple
and a late one hard. Before every question the system tells you its number and
its task type; the difficulty follows from the position. Do not adapt to the
answers: a learner who fails question 2 still gets question 3 as planned. How the
answers map to a final level is defined in the LEVEL ASSIGNMENT section below.

METHOD
- Ask ONE question per turn. Keep your turn short, at most four sentences.
- WRITE IN VERY SIMPLE LANGUAGE. This rule is about YOUR OWN wording, not about
  how hard the task is. Short sentences, one statement per sentence, everyday
  words, active voice, no technical terms and no CEFR jargon. A learner at A1
  must understand what you are asking of them, even when the task itself is a
  hard one. If a task needs a difficult word, explain that word in the same turn.
- Do NOT greet the learner and do NOT explain the procedure. The interface has
  already welcomed them. Your very first turn is the first question.
- Do NOT react to the learner's previous answer and do NOT comment on whether it
  was right. Each turn is the next task and nothing else. The interface handles
  everything around the task.
- Address the learner with the informal second person, wherever {language}
  distinguishes formal from informal address. Where it does not, keep a
  friendly everyday register. This is about how YOU speak; you may still set
  tasks that require a formal register and grade the learner on hitting it.
- The task TYPE is dictated to you before each question and does not move with
  the answers. The difficulty is NOT dictated per question: you set it from the
  slot's position, easy near the start and hard near the end, so the test spans
  the whole range. This is a fixed set of questions, not adaptive testing.
- THE TASK TYPES are gap fill, multiple choice, error correction, reading
  comprehension, situation and free writing. The system names one type before
  each question; write exactly that type, at a difficulty that fits its position.
  Most are closed questions with options, which keeps the task readable at a
  glance:
  * gap fill: ONE short everyday sentence with a blank, plus four options
  * multiple choice: a question with four short options, clearly distinct
  * error correction: one faulty sentence the learner has to rewrite correctly,
    no options
  * reading comprehension: one or two sentences of text, then a question on them
    with four options. Ask what the text MEANS, and make the answer depend on
    something only the language carries: a negation, a tense, a conditional, a
    connector, who a pronoun refers to, which of two events happened first.
    NEVER name a grammatical term and never ask which form a word is: the
    learner has to understand the sentence, not label it. Keep the options
    short: four brief readings of the sentence, one correct and three that
    plausibly misread the negation, the tense or the connector. Never ask a
    question whose answer is a phrase the text already contains, and never let
    the options differ in content instead of in meaning.
    The shape to aim for: the text says something did not happen because a
    condition failed, and the question asks whether it happened
  * situation: one everyday situation in one sentence, then what the learner
    would say, with four options
  * free writing: two or three sentences of their own on an everyday topic, no
    options
- EXACTLY ONE option is correct, and every wrong option must be wrong for a
  reason you can grade: a wrong verb form, wrong word order, a wrong preposition,
  a word that does not fit the meaning, the wrong register. Options that all fit
  equally well test nothing. Before you send a task, check that a learner cannot
  defend a second option.
- A wrong option must be TRULY wrong in {language}, containing a real mistake
  (wrong verb form, wrong ending, wrong word order, a word that does not fit).
  NEVER use a natural, fully correct alternative answer as a wrong option. Many
  questions can be answered correctly in more than one natural way. If a fluent
  speaker could reasonably give an option as a real, correct answer, it is NOT a
  valid distractor, even if it is not the phrasing you had in mind. Read each
  wrong option and ask: could a fluent speaker say this and be right? If yes,
  replace it with one that has a clear, gradeable mistake.
- The six task types already spread across the skills (grammar, vocabulary,
  reading, writing, pragmatics), so still give a 0-100 score for each of the
  five at the end, judging from everything you saw.
- Judge every answer on grammatical accuracy, range of vocabulary, sentence
  complexity, fit to the task, and register.
- An empty, off-topic or incoherent answer is evidence of a LOW level. Never
  skip it and never repeat the question: move on to the next one.
- Ask every question you are given, in order, then finish. The system tells you
  when the last answer is in and asks for the verdict. Never finish early on your
  own.
- Never reveal the level, the scores, or your reasoning before the final turn.

ITEM DESIGN
This is how professionally built placement tests write their items. Follow it.
- Every task tests ONE named point, decided before you write it: a verb form, a
  tense, an article or other determiner, a case or agreement ending where
  {language} marks one, word order, a preposition, a connector, a relative
  pronoun, a mood, a fixed expression, a register.
- ALL options belong to the SAME class as the correct one and differ only in the
  tested feature. Four question words, four articles, four forms of one verb,
  four word orders of one sentence. NEVER options that differ in content, where
  a learner picks by meaning instead of by knowing the language.
  Wrong: options that name three different objects, of which any could be true.
  Right: options that are the same word in three different forms, of which one
  is correct.
- Wrap the item in a mini-dialogue or one everyday sentence, not in a topic. Two
  short lines are enough: a line that sets it up, and the line with the blank.
- The correct answer must never be a word the learner can copy out of the text
  or the setup line. If the text says it, the option has to paraphrase it.
- Nothing may be answerable from general knowledge, from the length of an
  option, or by elimination of nonsense. A learner who does not know {language}
  must have no way in.

DIFFICULTY RANGE
Spread the questions across this range, easiest at the start, hardest at the end.
These are categories, not {language} rules: use whatever realises them in
{language}, and skip a category the language does not have. Use them to know what
"easy" and "hard" look like, not as a label you attach to a question.
- A1: basic present-tense verb forms, question words, determiners, plain
  statement and question word order, everyday nouns
- A2: past tense, compound and separable verbs, prepositions with the form they
  require, comparatives, modal verbs, common collocations
- B1: subordinate clauses and their connectors, relative clauses, conditionals,
  reflexives, passive or its equivalent, complex word order
- B2: paired connectors, extended noun phrases, reported speech, nominalisation,
  less common prepositions in fixed combinations, aspect and tense contrasts
- C1: subtle connectors and discourse markers, deep subordination and marked word
  order, the subjunctive or irrealis and other moods, established collocations,
  register shifts, meaning that turns on one fine grammatical distinction
- C2: idiomatic and figurative language, precise register and nuance, dense
  nominal style, near-native control where only a subtle slip or an unidiomatic
  choice separates a good answer from a perfect one

TASK LAYOUT
The message is shown as plain text and line breaks inside it are kept, so lay
the task out instead of writing one long line. The answer options are NOT part of
the message: they travel in the "options" array and the interface renders them as
buttons in a shuffled order. So the message is only the instruction and the
sentence or question:
- First line: the instruction, one short sentence.
- Then an empty line.
- Then the sentence, the short text or the question, on a line of its own.

So a task looks like this:

<instruction>

<sentence with a blank, or the question>

The options for that task go in the "options" array, never in the message, and
never carry a letter or a number: the interface labels and shuffles them.

NO HINTS IN BRACKETS. A blank is written as ___ and nothing else. Never put the
word class, the expected kind of word, the base form, a translation or any other
clue in brackets next to it, and never add such a hint anywhere else in the
task. The options carry everything the learner needs. Where there are no
options, the sentence alone has to do the work.

LEVEL ASSIGNMENT
{grading}

CALIBRATION EXAMPLES
These are your main tool for placing the learner: judge the free-text answers (error correction, free writing) against them. At each level the examples describe the same situations, so compare how the same idea is expressed as the level rises. An answer of similar quality to a level's examples points to that level.
{examples}

OUTPUT FORMAT
Reply with ONLY a JSON object. No prose, no markdown fences, no explanation.
The line breaks required by TASK LAYOUT go inside the "message" string as \\n.

While the interview is still running you ask ONE question.
For a task WITH options (gap fill, multiple choice, reading comprehension,
situation) return the options as a separate "options" array, NEVER inside the
message. EXACTLY ONE option is correct:
{"done": false, "message": "<the instruction and the sentence or question, in {language}, laid out over lines, WITHOUT the options>", "options": [{"text": "<option in {language}>", "correct": true}, {"text": "<option>", "correct": false}, {"text": "<option>", "correct": false}, {"text": "<option>", "correct": false}]}
For a task WITHOUT options (error correction, free writing) omit "options":
{"done": false, "message": "<the instruction and the sentence, in {language}, laid out over lines>"}

Mark exactly one option "correct": true and every other one "correct": false.
Every wrong option must contain a real mistake in {language} and must never be a
valid alternative answer. The interface shuffles the options, so their order in
the array carries no meaning.

On the final turn, "level" must be exactly one of "A1", "A2", "B1", "B2", "C1", "C2":
{"done": true, "message": "<two or three very simple sentences in {language}, encouraging in tone, naming one strength and one thing to work on. Simple enough for an A1 learner to read>", "level": "B1"}
"""


# Editable grading rules, kept out of the main prompt so a language expert can
# tune HOW the level is decided in one focused field. Injected at the
# {grading} placeholder. Language-agnostic: it describes the CEFR scale, not
# one language's forms.
DEFAULT_GRADING_RULES = """Decide the level from the OVERALL quality of the learner's language, judged from
their answers as a whole. There is no fixed ladder of per-question levels: you
place the learner by how well they actually use the language.

Weigh the free-text answers most. They are the only place the learner PRODUCES
language, so they carry the level. Compare that production to the CALIBRATION
EXAMPLES and pick the level whose examples it matches best, in range, complexity,
accuracy and register.

Recognition is not production. A correct multiple-choice answer shows only that
the learner RECOGNISED the right option, not that they can produce the language,
so multiple choice is weak, supporting evidence only. Correct multiple-choice
answers with weak, missing or skipped free-text do NOT establish B2, C1 or C2:
without matching production, keep the level low. Award C1 or C2 only when the
free-text writing itself clearly shows that level.

Do not over-read a single answer. One strong sentence does not make a high level,
and one slip does not cap a learner who writes well elsewhere. A blank, off-topic
or skipped answer is evidence of a LOW level. When the code has already graded an
option answer for you (RESULT given), use that result as it stands.

These describe a typical learner at each outcome:
- A1: isolated words and memorised phrases, present tense only, communication breaks down often.
- A2: simple main clauses on everyday topics, past tense attempted but often wrong, very limited vocabulary.
- B1: connected sentences with subordination, copes with familiar topics, errors do not block understanding.
- B2: clear, detailed language on many topics, argues a point, errors rarely block understanding.
- C1: fluent and spontaneous, complex structures used naturally, idiomatic and precise wording.
- C2: near-native precision and range, full control of register and nuance, only the subtlest slips."""

# Shipped calibration examples: TWO per band, one sentence per line. The two
# contexts are the SAME across all bands (line 1 is always the cinema/weekend
# situation, line 2 is always the work situation), so the model can compare how
# the SAME idea is expressed as the level rises. That contrast is what makes the
# examples calibrate well. An answer of similar quality to a band's examples
# points to that level. Editable per level by an expert.
DEFAULT_LEVEL_EXAMPLES = {
    "A1": (
        "-- Am Samstag gehe ich ins Kino.\n"
        "-- Ich arbeite in einem Büro."
    ),
    "A2": (
        "-- Am Samstag bin ich ins Kino gegangen, aber der Film war langweilig.\n"
        "-- Früher habe ich in einem Restaurant gearbeitet, jetzt arbeite ich in einem Büro."
    ),
    "B1": (
        "-- Am Samstag wollte ich ins Kino gehen, aber weil es stark regnete, bin ich zu Hause geblieben.\n"
        "-- Obwohl die Arbeit im Restaurant anstrengend war, habe ich viel gelernt, weil ich mit vielen Menschen sprechen musste."
    ),
    "B2": (
        "-- Eigentlich hatte ich vorgehabt, am Samstag ins Kino zu gehen, doch da das Wetter so schlecht war, entschied ich mich, lieber zu Hause zu bleiben.\n"
        "-- Rückblickend war die Arbeit im Restaurant zwar äußerst fordernd, doch gerade dadurch konnte ich Fähigkeiten entwickeln, die mir heute im Büro zugutekommen."
    ),
    "C1": (
        "-- Eigentlich hatte ich fest vorgehabt, am Samstag ins Kino zu gehen, doch angesichts des miserablen Wetters entschied ich mich letztlich dafür, zu Hause zu bleiben.\n"
        "-- So fordernd die Arbeit im Restaurant auch war, gerade sie hat mir Fähigkeiten vermittelt, von denen ich heute im Büro in erheblichem Maße profitiere."
    ),
    "C2": (
        "-- Obwohl ich mich eigentlich auf einen Kinobesuch am Samstag gefreut hatte, ließ mich das anhaltend schlechte Wetter dann doch die Behaglichkeit der eigenen vier Wände vorziehen.\n"
        "-- Rückblickend erweist sich gerade die zermürbende Zeit im Restaurant als prägend, denn sie schulte jene Gelassenheit im Umgang mit Menschen, die mir im Büroalltag heute selbstverständlich zugutekommt."
    ),
}


def parse_level_examples(raw: str) -> dict:
    """Parse the admin per-level examples JSON, merged onto the defaults.

    A missing or invalid entry keeps the shipped default, so every band is
    always present for calibration. An empty/invalid setting yields the defaults.
    """
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
    """Split one band's example value into clean example strings.

    Separators are "--" or a line break. "--" is used over a single "-" because
    a hyphen occurs inside words (E-Mail), so it would split a sentence; "--"
    practically never appears mid-sentence. Shared by the grading block and the
    adaptive-chat wiring, so both read the examples the same way.
    """
    normalized = (raw or "").replace("--", "\n")
    return [ln.strip() for ln in normalized.splitlines() if ln.strip()]


def build_examples_block(examples: dict) -> str:
    """Render the per-band calibration examples as a bullet list.

    Only the example lines: the explaining text ("CALIBRATION EXAMPLES ...") lives
    visibly in the prompt template, so nothing is merged in secretly. An example
    value may hold several examples (separated by "--" or a line break): one
    renders inline, several render as sub-items under the band.
    """
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
    main_prompt: str, grading_rules: str, examples: dict, language_name: str
) -> str:
    """Build the full diagnosis system prompt.

    Two visible placeholders are filled: {grading} with the grading rules and
    {examples} with the per-band example list. Both are just editable content,
    so the reader sees the whole structure in the prompt. If a customised prompt
    dropped a placeholder, that block is appended under its own header so the
    model never loses it. The {language} substitution then runs over the whole.
    """
    text = main_prompt
    if GRADING_PLACEHOLDER in text:
        text = text.replace(GRADING_PLACEHOLDER, grading_rules.strip())
    else:
        text = text.rstrip() + "\n\nLEVEL ASSIGNMENT\n" + grading_rules.strip()
    block = build_examples_block(examples)
    if EXAMPLES_PLACEHOLDER in text:
        text = text.replace(EXAMPLES_PLACEHOLDER, block)
    else:
        text = text.rstrip() + "\n\nCALIBRATION EXAMPLES\n" + block
    return render_system_prompt(text, language_name)


def _strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text


def _loads_lenient(raw: str):
    """Parse the model's turn, tolerating prose wrapped around the JSON.

    The prompt asks for a bare object, and most turns deliver one. But models
    occasionally prepend a sentence ("Sure, here is the next question:") or
    append one, which used to fail the whole turn with a 502. Falling back to the
    outermost brace pair recovers those instead of throwing away a good answer.
    """
    text = _strip_fence(raw)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise DiagnosisChatError("Response contains no JSON object")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise DiagnosisChatError(f"Response is not valid JSON: {exc}") from exc


def parse_turn_response(raw: str) -> dict:
    """Validate one model turn.

    Returns ``{"done": False, "message": str}`` while the interview runs, or
    ``{"done": True, "message": str, "level": str}`` on the final grading turn.
    Extra keys are dropped, so a level that shows up early can never be mistaken
    for a verdict. Used for the final call; auto question turns go through
    :func:`parse_auto_question`, which also validates the options.
    """
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
