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
# dictates WHERE the correct option sits, cycling a -> b -> c -> d across the
# option-bearing questions. Models have a strong bias to put the answer at a),
# which makes the test feel broken ("the answer is always a"). Error correction
# and free writing have no options and are skipped.
OPTION_QUESTION_TYPES = {
    "gap fill",
    "multiple choice",
    "reading comprehension",
    "situation",
}
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


def parse_question_plan(raw: str) -> list[dict]:
    """Parse the admin question-plan JSON, falling back to the shipped default.

    Each item is ``{"band": <A1..B2>, "type": <one of VALID_QUESTION_TYPES>}``
    with an optional ``"text"`` verbatim question. Any structural problem returns
    the code default, so the diagnosis always has a usable plan.
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
        plan.append(step)
    return plan

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
# Used when the admin pinned a verbatim question text for this slot. The model
# must ask exactly this, only turning the layout into line breaks per the prompt.
NEXT_QUESTION_VERBATIM_MESSAGE = (
    "Now ask question {number} of {total}. Ask EXACTLY this question, word for "
    "word, changing nothing about its wording or its options:\n\n{text}\n\n"
    "Do not give any verdict yet: reply with done=false and only this one question."
)
# Appended for option-bearing questions to break the model's a) bias. The
# position is dictated, so the model must build the item so the CORRECT answer
# lands at that letter, with the other options plausible but clearly wrong.
CORRECT_POSITION_DIRECTIVE = (
    " Put the CORRECT option at position {letter}), not at a). Arrange the other "
    "options so only {letter}) is right, and keep them plausible."
)
# Sent back when the model tries to close before all questions are answered.
KEEP_GOING_MESSAGE = (
    "Only {asked} of {total} questions are answered. Do not finish yet and do "
    "not reveal any level. Reply with done=false and the next question."
)


def correct_option_letter(number: int, plan: list[dict]) -> str | None:
    """Which letter the correct option should sit at for this question.

    Cycles a -> b -> c across the option-bearing questions in order, so the
    correct answer is spread evenly instead of always landing at a). Returns
    ``None`` for questions with no options (error correction, free writing).
    """
    step = plan[number - 1]
    if step["type"] not in OPTION_QUESTION_TYPES:
        return None
    # Rank of this question among the option-bearing ones (0-based).
    rank = sum(1 for s in plan[:number] if s["type"] in OPTION_QUESTION_TYPES) - 1
    return CORRECT_OPTION_POSITIONS[rank % len(CORRECT_OPTION_POSITIONS)]


def next_question_message(number: int, plan: list[dict] | None = None) -> str:
    """The per-turn instruction fixing this question's number, type and band.

    ``plan`` defaults to the shipped ``QUESTION_PLAN``. When the slot carries a
    verbatim ``text``, the model is told to ask it word for word instead. For
    option-bearing questions the correct option's position is dictated too, so it
    does not always default to a).
    """
    steps = plan or QUESTION_PLAN
    step = steps[number - 1]
    total = len(steps)
    if step.get("text"):
        return NEXT_QUESTION_VERBATIM_MESSAGE.format(
            number=number, total=total, text=step["text"]
        )
    message = NEXT_QUESTION_MESSAGE.format(
        number=number, total=total, band=step["band"], type=step["type"]
    )
    letter = correct_option_letter(number, steps)
    if letter:
        message += CORRECT_POSITION_DIRECTIVE.format(letter=letter)
    return message


def keep_going_message(asked: int, total: int) -> str:
    """Nudge for a model that answered done=true before all questions were asked."""
    return KEEP_GOING_MESSAGE.format(asked=asked, total=total)


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
- From your SECOND turn on, put ONE short, warm reaction to what the learner
  just wrote into the separate "reaction" field, and keep "message" for the task
  alone. The interface shows the two as two chat bubbles, so never repeat the
  reaction inside "message". On your FIRST turn leave "reaction" empty.
  Vary the wording: a brief compliment, a simple acknowledgement, or a note that
  you are moving on to the next question. Keep the reaction to one sentence,
  keep it neutral about whether the answer was right, and never repeat the same
  opener twice.
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
  * multiple choice: a question with four options labelled a), b), c), d).
    Say once that the learner may simply reply with the letter, and keep the
    options short and clearly distinct
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
the task out instead of writing one long line.
- First line: the instruction, one short sentence.
- Then an empty line.
- Then the sentence, the short text or the question, on a line of its own.
- Then an empty line, then the answer options, ONE PER LINE, each on its own
  line and labelled a), b), c), d). Keep that empty line before the first option
  even when the task already has a text and a question above it.

So a task with options looks like this:

<instruction>

<sentence with a blank, or the question>

a) <option>
b) <option>
c) <option>
d) <option>

A task without options is the instruction, an empty line, and the sentence.

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

While the interview is still running, always use exactly these three keys:
{"done": false, "reaction": "<one short sentence in {language} about the answer you just read>", "message": "<your next question, written in {language}, without the reaction>"}

"reaction" is REQUIRED on every turn. The only turn where it may be an empty
string is your very first one, because there is no answer to react to yet.
Leaving it out later drops your reaction from the conversation entirely.

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
    ``{"done": True, "message": str, "level": str, "skill_scores": dict}`` on
    the final turn. Extra keys are dropped, so a level that shows up early can
    never be mistaken for a verdict.

    A running turn may carry ``reaction``, the one-sentence response to the
    learner's last answer, which the client shows as its own chat bubble. It is
    optional in both directions: the first turn has nothing to react to, and a
    model that ignores the field still produces a usable question.
    """
    parsed = _loads_lenient(raw)

    if not isinstance(parsed, dict):
        raise DiagnosisChatError("Response must be a JSON object")

    message = parsed.get("message")
    if not isinstance(message, str) or not message.strip():
        raise DiagnosisChatError("Missing or empty message")

    if not parsed.get("done"):
        turn = {"done": False, "message": message.strip()}
        reaction = parsed.get("reaction")
        # Only a non-empty string travels on: the field is absent on the first
        # turn, and an empty bubble would look like the assistant said nothing.
        if isinstance(reaction, str) and reaction.strip():
            turn["reaction"] = reaction.strip()
        return turn

    level = parsed.get("level")
    if level not in VALID_LEVELS:
        raise DiagnosisChatError(f"Invalid level: {level!r}")

    return {
        "done": True,
        "message": message.strip(),
        "level": level,
        "skill_scores": _validate_scores(parsed.get("skill_scores")),
    }
