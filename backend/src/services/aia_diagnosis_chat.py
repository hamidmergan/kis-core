"""Assessment as a short chat, everything didactic lives in the admin prompt."""

import json
import random

from src.services.aia_level_ladder import LEVELS, build_levels_block


PROMPT_PLACEHOLDER = "{language}"

# The six levels, the whole ladder from A1 to C2.
VALID_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}

# Fixed test size, every question is spelled out, the difficulty comes from the position.

# Two exercise kinds: choice graded in code, free text typed.
CHOICE_TYPE = "choice"
FREE_TEXT_TYPE = "free text"
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

# The position of the correct option is rolled again every time.

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


# The shipped German question set, spelled out in full.
DEFAULT_GERMAN_QUESTION_PLAN = [
    {
        "type": FREE_TEXT_TYPE,
        "text": ("Setze das Wort in Klammern in der richtigen Form ein.\n\n"
                 "Ich stehe früh auf und ___ (gehen) jeden Tag zur Arbeit."),
        "answers": ["gehe"],
    },
    {
        "type": CHOICE_TYPE,
        "text": "Welches Wort passt?\n\n___ Buch liegt auf dem Tisch.",
        "options": [
            {"text": "Das", "correct": True},
            {"text": "Der", "correct": False},
            {"text": "Die", "correct": False},
            {"text": "Den", "correct": False},
        ],
    },
    {
        "type": FREE_TEXT_TYPE,
        "text": "Der Satz hat einen Fehler. Schreibe ihn richtig.\n\nGestern ich habe einen Film gesehen.",
    },
    {
        "type": CHOICE_TYPE,
        "text": "Welches Wort passt?\n\nIch fahre mit ___ Bus zur Uni.",
        "options": [
            {"text": "dem", "correct": True},
            {"text": "den", "correct": False},
            {"text": "das", "correct": False},
            {"text": "der", "correct": False},
        ],
    },
    {
        "type": CHOICE_TYPE,
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
        "type": CHOICE_TYPE,
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
        "type": CHOICE_TYPE,
        "text": "Welche Wörter passen in die Lücken?\n\n___ mehr man übt, ___ besser wird man.",
        "options": [
            {"text": "Je … desto", "correct": True},
            {"text": "Wenn … dann", "correct": False},
            {"text": "So … wie", "correct": False},
            {"text": "Umso … je", "correct": False},
        ],
    },
    {
        "type": FREE_TEXT_TYPE,
        "text": ("Schreibe zwei bis drei Sätze.\n\n"
                 "Beschreibe, was du letztes Wochenende gemacht hast."),
    },
    {
        "type": CHOICE_TYPE,
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
        "type": FREE_TEXT_TYPE,
        "text": ("Der Satz hat einen Fehler. Schreibe ihn richtig.\n\n"
                 "Je länger die Sitzung dauerte, desto ungeduldiger wurden die Teilnehmer, "
                 "trotz sie sich vorgenommen hatten, ruhig zu bleiben."),
    },
    {
        "type": FREE_TEXT_TYPE,
        "text": ("Schreibe drei bis vier Sätze.\n\n"
                 "Nimm Stellung: Sollten Universitäten eine Anwesenheitspflicht in "
                 "Vorlesungen verlangen? Begründe deine Meinung."),
    },
    {
        "type": CHOICE_TYPE,
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


# Appended once all questions are answered, to pull the verdict out.
FORCE_FINISH_MESSAGE = (
    "That was the learner's last answer. Do not ask another question. "
    "Reply now with the final JSON object: done=true, message and level."
)


# The user turn that carries the finished record to the single final grading call.
FINAL_INSTRUCTION = (
    "The learner has answered every question. The full record follows. Apply the "
    "LEVEL ASSIGNMENT rules and reply with ONLY the final JSON object: done=true, "
    "message and level. Where a RESULT is given, use it as it stands."
)


def build_final_messages(system_prompt: str, plan: list[dict], history: list[dict]) -> list[dict]:
    """The messages for the one grading call."""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": FINAL_INSTRUCTION + "\n\n" + build_grading_brief(plan, history)},
    ]


# Sent after an unreadable answer.
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
- THERE ARE TWO TASK TYPES, choice and free text. The system names one before
  each question; write exactly that type, at a difficulty that fits its position.
  * choice: a question with four short options, clearly distinct, exactly one
    correct. Whatever the task needs BEFORE the question goes into the question
    text itself: nothing at all, or one or two sentences of reading, or one
    everyday situation. When you set a reading task, ask what the text MEANS and
    make the answer depend on something only the language carries: a negation, a
    tense, a conditional, a connector, who a pronoun refers to, which of two
    events happened first. NEVER name a grammatical term and never ask which
    form a word is: the learner has to understand the sentence, not label it.
    Never ask a question whose answer is a phrase the text already contains, and
    never let the options differ in content instead of in meaning.
  * free text: no options, the learner writes the answer. Two shapes, and the
    system says which one the slot wants:
    - with a solution: ONE short everyday sentence with a blank, written as ___ ,
      that leaves exactly one word fitting. If several words would fit, add
      enough context that only one does.
    - without a solution: the learner produces language of their own, either one
      faulty sentence to rewrite correctly, or two or three sentences on an
      everyday topic or a question to take a position on.
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
- The tasks together already spread across the skills (grammar, vocabulary,
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

These describe a typical learner at each outcome:
{levels}

CALIBRATION EXAMPLES
These are your main tool for placing the learner: judge the free-text answers the learner wrote themselves against them. At each level the examples describe the same situations, so compare how the same idea is expressed as the level rises. An answer of similar quality to a level's examples points to that level.
{examples}

OUTPUT FORMAT
Reply with ONLY a JSON object. No prose, no markdown fences, no explanation.
The line breaks required by TASK LAYOUT go inside the "message" string as \\n.

While the interview is still running you ask ONE question.
For a choice task return the options as a separate "options" array, NEVER inside
the message. EXACTLY ONE option is correct:
{"done": false, "message": "<the instruction and the sentence or question, in {language}, laid out over lines, WITHOUT the options>", "options": [{"text": "<option in {language}>", "correct": true}, {"text": "<option>", "correct": false}, {"text": "<option>", "correct": false}, {"text": "<option>", "correct": false}]}
For a free-text task omit "options":
{"done": false, "message": "<the instruction and the sentence, in {language}, laid out over lines>"}

Mark exactly one option "correct": true and every other one "correct": false.
Every wrong option must contain a real mistake in {language} and must never be a
valid alternative answer. The interface shuffles the options, so their order in
the array carries no meaning.

On the final turn, "level" must be exactly one of "A1", "A2", "B1", "B2", "C1", "C2":
{"done": true, "message": "<two or three very simple sentences in {language}, encouraging in tone, naming one strength and one thing to work on. Simple enough for an A1 learner to read>", "level": "B1"}
"""


# The old default stays so it is recognised on read.
_LEGACY_GRADING_RULES = """Decide the level from the OVERALL quality of the learner's language, judged from
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

# The grading rules as their own field, they only describe the method.
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
option answer for you (RESULT given), use that result as it stands."""

# Two example sentences per level, always the same two situations.
DEFAULT_LEVEL_EXAMPLES = {
    "A1": (
        "Am Samstag gehe ich ins Kino.\n"
        "Ich arbeite in einem Büro."
    ),
    "A2": (
        "Am Samstag bin ich ins Kino gegangen, aber der Film war langweilig.\n"
        "Früher habe ich in einem Restaurant gearbeitet, jetzt arbeite ich in einem Büro."
    ),
    "B1": (
        "Am Samstag wollte ich ins Kino gehen, aber weil es stark regnete, bin ich zu Hause geblieben.\n"
        "Obwohl die Arbeit im Restaurant anstrengend war, habe ich viel gelernt, weil ich mit vielen Menschen sprechen musste."
    ),
    "B2": (
        "Eigentlich hatte ich vorgehabt, am Samstag ins Kino zu gehen, doch da das Wetter so schlecht war, entschied ich mich, lieber zu Hause zu bleiben.\n"
        "Rückblickend war die Arbeit im Restaurant zwar äußerst fordernd, doch gerade dadurch konnte ich Fähigkeiten entwickeln, die mir heute im Büro zugutekommen."
    ),
    "C1": (
        "Eigentlich hatte ich fest vorgehabt, am Samstag ins Kino zu gehen, doch angesichts des miserablen Wetters entschied ich mich letztlich dafür, zu Hause zu bleiben.\n"
        "So fordernd die Arbeit im Restaurant auch war, gerade sie hat mir Fähigkeiten vermittelt, von denen ich heute im Büro in erheblichem Maße profitiere."
    ),
    "C2": (
        "Obwohl ich mich eigentlich auf einen Kinobesuch am Samstag gefreut hatte, ließ mich das anhaltend schlechte Wetter dann doch die Behaglichkeit der eigenen vier Wände vorziehen.\n"
        "Rückblickend erweist sich gerade die zermürbende Zeit im Restaurant als prägend, denn sie schulte jene Gelassenheit im Umgang mit Menschen, die mir im Büroalltag heute selbstverständlich zugutekommt."
    ),
}


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
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text


def _loads_lenient(raw: str):
    """Reads the model answer even when prose surrounds the JSON."""
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
