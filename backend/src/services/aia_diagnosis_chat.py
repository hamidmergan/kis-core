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

# The four outcomes. Everything above B1 collapses into "B1+" ("über B1"): the
# test exists to find who needs language support, and a learner past B1 needs
# none, so telling C1 from C2 would be effort without a consequence. "B1+" is
# the stored code; the frontend renders it as "Über B1".
VALID_LEVELS = {"A1", "A2", "B1", "B1+"}
REQUIRED_SKILLS = {"grammar", "vocabulary", "reading", "writing", "pragmatics"}

# Fixed-length test. Every learner answers the same eight questions, so two
# results are comparable and the UI can show "question 3 of 8". The six task types
# each appear (gap fill, multiple choice, error correction, reading, situation,
# free writing); the two extra slots are quick multiple-choice quizzes, so MC runs
# three times. Two questions per band give a second signal, so one lucky or unlucky
# answer cannot flip the level. The bands rise A1 to B2, and the two MC extras sit
# at A1 and B2 to round each band to two. The OUTCOME set is only four (A1..B1+);
# coping with the B2 pair is what earns B1+. Index 0 is question 1.
QUESTION_PLAN = [
    {"band": "A1", "type": "gap fill"},
    {"band": "A1", "type": "multiple choice"},
    {"band": "A2", "type": "error correction"},
    {"band": "A2", "type": "multiple choice"},
    {"band": "B1", "type": "reading comprehension"},
    {"band": "B1", "type": "situation"},
    {"band": "B2", "type": "multiple choice"},
    {"band": "B2", "type": "free writing"},
]
QUESTION_COUNT = len(QUESTION_PLAN)
# Kept as a flat list too, since the difficulty ladder is what most callers read.
QUESTION_BANDS = [step["band"] for step in QUESTION_PLAN]

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

# The four bands that carry a calibration example. B1+ needs none of its own: a
# B2-quality answer IS the signal for B1+ (it means the learner coped past B1).
EXAMPLE_LEVELS = ["A1", "A2", "B1", "B2"]

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
VALID_BANDS = {"A1", "A2", "B1", "B2"}


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

    Each item is ``{"band": <A1..B2>, "type": <one of VALID_QUESTION_TYPES>}``.
    Optional authoring fields:
      * ``"text"``   the verbatim question shown to the learner.
      * ``"options"`` (option types only) the answer options, each with a
        ``correct`` flag. Graded in code, so no model call. A structurally broken
        option set reverts the whole plan to the default (existing philosophy:
        always run on a usable plan).
      * ``"example"`` (free-text types only) a sample good answer for the final
        LLM to calibrate against.
    Options on a free-text type, or an example on an option type, are simply
    dropped rather than rejected, so a stray field from the editor is forgiving.
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
        band, qtype = item.get("band"), item.get("type")
        if band not in VALID_BANDS or qtype not in VALID_QUESTION_TYPES:
            return QUESTION_PLAN
        step = {"band": band, "type": qtype}
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            step["text"] = text.strip()
        if qtype in OPTION_QUESTION_TYPES and item.get("options") is not None:
            options = _parse_options(item.get("options"))
            if options is None:
                return QUESTION_PLAN
            step["options"] = options
        if qtype in FREE_TEXT_QUESTION_TYPES:
            example = item.get("example")
            if isinstance(example, str) and example.strip():
                step["example"] = example.strip()
        plan.append(step)
    return plan


# Shipped German question set. Unlike QUESTION_PLAN (band/type only, one prompt
# for every language), these are fully authored: real German text, options with a
# correct flag, and example answers for the free-text slots. A German diagnosis
# with no admin config uses this, so the common case runs instantly with ZERO
# model calls. Any OTHER language falls back to QUESTION_PLAN and the model
# generates the items, so the test stays language-agnostic out of the box. The
# admin can edit or replace all of it. Each item follows the item-design rules:
# exactly one correct option, and every distractor a real, gradeable mistake.
GERMAN_LANGUAGE_CODE = "de"
DEFAULT_GERMAN_QUESTION_PLAN = [
    {
        "band": "A1", "type": "gap fill",
        "text": "Setze das passende Wort ein.\n\nIch ___ jeden Tag zur Arbeit.",
        "options": [
            {"text": "gehe", "correct": True},
            {"text": "gehst", "correct": False},
            {"text": "geht", "correct": False},
            {"text": "gehen", "correct": False},
        ],
    },
    {
        "band": "A1", "type": "multiple choice",
        "text": "Welches Wort passt?\n\n___ Buch liegt auf dem Tisch.",
        "options": [
            {"text": "Das", "correct": True},
            {"text": "Der", "correct": False},
            {"text": "Die", "correct": False},
            {"text": "Den", "correct": False},
        ],
    },
    {
        "band": "A2", "type": "error correction",
        "text": "Der Satz hat einen Fehler. Schreibe ihn richtig.\n\nGestern ich habe einen Film gesehen.",
        "example": "Gestern habe ich einen Film gesehen.",
    },
    {
        "band": "A2", "type": "multiple choice",
        "text": "Welches Wort passt?\n\nIch fahre mit ___ Bus zur Uni.",
        "options": [
            {"text": "dem", "correct": True},
            {"text": "den", "correct": False},
            {"text": "das", "correct": False},
            {"text": "der", "correct": False},
        ],
    },
    {
        "band": "B1", "type": "reading comprehension",
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
        "band": "B1", "type": "situation",
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
        "band": "B2", "type": "multiple choice",
        "text": "Welche Wörter passen in die Lücken?\n\n___ mehr man übt, ___ besser wird man.",
        "options": [
            {"text": "Je … desto", "correct": True},
            {"text": "Wenn … dann", "correct": False},
            {"text": "So … wie", "correct": False},
            {"text": "Umso … je", "correct": False},
        ],
    },
    {
        "band": "B2", "type": "free writing",
        "text": ("Schreibe zwei bis drei Sätze.\n\n"
                 "Beschreibe, was du letztes Wochenende gemacht hast."),
        "example": ("Am Samstag habe ich lange geschlafen und danach Freunde getroffen. "
                    "Am Sonntag bin ich spazieren gegangen, weil das Wetter schön war."),
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
    :func:`parse_question_plan`: band and type must be known, an option set (option
    types only) must pass ``_parse_options``, and text/example must be strings.
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
        if item.get("band") not in VALID_BANDS or item.get("type") not in VALID_QUESTION_TYPES:
            return False
        if item.get("text") is not None and not isinstance(item.get("text"), str):
            return False
        if item.get("example") is not None and not isinstance(item.get("example"), str):
            return False
        if item["type"] in OPTION_QUESTION_TYPES and item.get("options") is not None:
            if _parse_options(item.get("options")) is None:
                return False
    return True


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
        step = plan[i] if i < len(plan) else {"band": "?", "type": "?"}
        band, qtype = step.get("band", "?"), step.get("type", "?")
        mode = question_mode(step)
        header = f"Question {i + 1} ({band}, {qtype})"
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
            example = step.get("example")
            extra = f" A good answer looks like: {example}." if example else ""
            lines.append(
                f"{header}: authored free-text task. Question: {q_text} "
                f"Learner answered: \"{answer}\".{extra} Judge the answer for this band."
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
                f"Learner answered: \"{answer}\". Judge the answer for this band."
            )
    return "\n\n".join(lines)


# Sent as the first user turn so the model always sees a user role before it
# speaks. Never shown to the learner.
KICKOFF_MESSAGE = "Begin the interview now with your first question."
# Appended once all questions are answered, to pull the verdict out.
FORCE_FINISH_MESSAGE = (
    "That was the learner's last answer. Do not ask another question. "
    "Reply now with the final JSON object: done=true, level and skill_scores."
)
# Injected on every asking turn so the model does not have to count the
# transcript itself: the backend knows the position and dictates both the task
# type and the band for this one question.
NEXT_QUESTION_MESSAGE = (
    "Now ask question {number} of {total}. It must be a {type} task at CEFR "
    "{band} difficulty, no easier and no harder, whatever the learner answered "
    "before. Do not give any verdict yet: reply with done=false and only this "
    "one question."
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
    """The per-turn instruction that fixes an auto question's number, type and band.

    ``plan`` defaults to the shipped ``QUESTION_PLAN``. A slot with a verbatim
    ``text`` is asked word for word; otherwise the band and type are dictated. For
    option types the structured-options directive is appended so the model returns
    the options as data, not as a), b), c), d) inside the message.
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
            number=number, total=total, band=step["band"], type=step["type"]
        )
    if step["type"] in OPTION_QUESTION_TYPES:
        message += AUTO_OPTIONS_DIRECTIVE
    return message


# The user turn that carries the finished record to the single final grading call.
FINAL_INSTRUCTION = (
    "The learner has answered every question. The full record follows. Apply the "
    "LEVEL ASSIGNMENT rules and reply with ONLY the final JSON object: done=true, "
    "message, level and skill_scores. Where a RESULT is given, use it as it stands."
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
Sort the learner into one of four levels, A1, A2, B1, or B1+ (anything above
B1), and give a score from 0 to 100 for each of: grammar, vocabulary, reading,
writing, pragmatics. B1+ means the learner needs no language support, so there
is no point telling B2 from C1 or C2: they all become B1+.

THE TEST IS A FIXED STAIRCASE
You ask exactly 8 questions on a rising ladder, two per band: questions 1-2 at
A1, 3-4 at A2, 5-6 at B1, 7-8 at B2. Both the task type AND the difficulty are
FIXED by position and do NOT adapt to the answers. Before each question the
system tells you the number, the task type and the difficulty. Follow it
exactly. How the answers map to a final level is defined in the LEVEL ASSIGNMENT
section below.

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
- Neither the difficulty NOR the task type is yours to choose. Both are dictated
  to you before you write each question, and they do not move with the answers.
  A learner who fails question 2 still gets the question-3 task as assigned. This
  is a fixed staircase, not adaptive testing.
- THE TASK TYPES, fixed per question: gap fill (Q1), multiple choice (Q2, Q4, Q7),
  error correction (Q3), reading comprehension (Q5), situation (Q6), free writing
  (Q8). Multiple choice is used three times, at A1, A2 and B2. Write exactly the
  type the system names. Most are closed questions with options, which keeps the
  task readable at a glance:
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
- Ask exactly 8 questions, then finish. The system tells you when the last
  answer is in and asks for the verdict. Never finish early on your own.
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

DIFFICULTY LADDER
For each question you are told its band. Pick the point you test from that band.
These are categories, not {language} rules: use whatever realises them in
{language}, and skip a category the language does not have.
- A1 (questions 1-2): basic present-tense verb forms, question words, determiners,
  plain statement and question word order, everyday nouns
- A2 (questions 3-4): past tense, compound and separable verbs, prepositions with
  the form they require, comparatives, modal verbs, common collocations
- B1 (questions 5-6): subordinate clauses and their connectors, relative clauses,
  conditionals, reflexives, passive or its equivalent, complex word order
- B2 (questions 7-8): paired connectors, extended noun phrases, reported speech,
  nominalisation, less common prepositions in fixed combinations, aspect and
  tense contrasts. Coping here is what separates B1+ from B1

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
Use these example answers to judge free-text answers (error correction, free writing). At each band the examples describe the same situations, so compare how the same idea is expressed as the level rises. An answer of similar quality to a band's examples points to that level. A B2-quality answer means the learner copes past B1, so B1+.
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

On the final turn, "level" must be exactly one of "A1", "A2", "B1", "B1+":
{"done": true, "message": "<two or three very simple sentences in {language}, encouraging in tone, naming one strength and one thing to work on. Simple enough for an A1 learner to read>", "level": "B1", "skill_scores": {"grammar": 60, "vocabulary": 55, "reading": 65, "writing": 50, "pragmatics": 60}}
"""


# Editable grading rules, kept out of the main prompt so a language expert can
# tune HOW the level is decided in one focused field. Injected at the
# {grading} placeholder. Language-agnostic: it describes the CEFR scale, not
# one language's forms.
DEFAULT_GRADING_RULES = """Decide the final level from how high up the ladder the learner still copes.
- Copes with the A1 questions but not the A2 questions: A1.
- Copes with the A2 questions but not the B1 questions: A2.
- Copes with the B1 questions but not the B2 questions: B1.
- Copes with the B2 questions too: B1+.
B1+ is everything above B1, so do not split it into B2, C1 or C2.

Read the ladder as a ceiling, not a checklist. The level is the HIGHEST band the
learner still handles SOLIDLY (both of that band's two questions). A single slip
lower down, when the learner clearly copes higher up, is noise: do not let it cap
the level. But do NOT promote on a single lucky hit: getting only one of a band's
two questions is not coping with that band. When the code has already graded an
option answer for you (RESULT given), use that result as it stands.

These describe a typical learner at each outcome:
- A1: isolated words and memorised phrases, present tense only, communication breaks down often.
- A2: simple main clauses on everyday topics, past tense attempted but often wrong, very limited vocabulary.
- B1: connected sentences with subordination, copes with familiar topics, errors do not block understanding.
- B1+: everything above B1, needs no language support, copes with the B2 questions too."""

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
}


def parse_level_examples(raw: str) -> dict:
    """Parse the admin per-level examples JSON, merged onto the defaults.

    A missing or invalid entry keeps the shipped default, so all four bands are
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


def _validate_scores(raw_scores) -> dict[str, int]:
    if not isinstance(raw_scores, dict):
        raise DiagnosisChatError("skill_scores must be an object")
    missing = REQUIRED_SKILLS - raw_scores.keys()
    if missing:
        raise DiagnosisChatError(f"Missing skill scores: {sorted(missing)}")
    scores: dict[str, int] = {}
    for skill in REQUIRED_SKILLS:
        value = raw_scores[skill]
        # bool is an int subclass; a True score is a malformed answer, not a 1.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DiagnosisChatError(f"skill_scores.{skill} must be a number, got {value!r}")
        if not 0 <= value <= 100:
            raise DiagnosisChatError(f"skill_scores.{skill} must be 0-100, got {value!r}")
        scores[skill] = int(value)
    return scores


def parse_turn_response(raw: str) -> dict:
    """Validate one model turn.

    Returns ``{"done": False, "message": str}`` while the interview runs, or
    ``{"done": True, "message": str, "level": str, "skill_scores": dict}`` on the
    final grading turn. Extra keys are dropped, so a level that shows up early can
    never be mistaken for a verdict. Used for the final call; auto question turns
    go through :func:`parse_auto_question`, which also validates the options.
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
        "skill_scores": _validate_scores(parsed.get("skill_scores")),
    }
