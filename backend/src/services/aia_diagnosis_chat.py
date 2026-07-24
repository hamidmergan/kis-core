"""Language diagnosis as a short adaptive chat interview.

The learner's CEFR level used to come from a fixed 12-question form whose items
were hardcoded in one language. This module replaces that with a chat: the
model asks one question at a time, adapts to the answers, and closes with a
verdict. Everything didactic lives in the prompt, which an admin edits centrally
(setting ``language_diagnosis_prompt``), so a language expert can change the
method without a code change.

The prompt is language-agnostic. It carries the CEFR anchors, which are the same
scale for every language, and takes the actual target language through the
``{sprache}`` placeholder. That is why there is ONE prompt rather than one per
language.

Substitution is a plain ``str.replace``, never ``str.format``: the template
contains a JSON example full of braces, and it is free text an admin types.
"""

import json


PROMPT_PLACEHOLDER = "{sprache}"

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
# History caps. The client keeps the transcript and posts it back each turn, so
# these bound how big a single request may grow.
MAX_HISTORY_MESSAGES = 40
MAX_MESSAGE_CHARS = 2000
# Ceiling for the admin-edited prompt, so a paste accident cannot blow up every
# diagnosis request.
MAX_PROMPT_CHARS = 20000

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
# Sent back when the model tries to close before all questions are answered.
KEEP_GOING_MESSAGE = (
    "Only {asked} of {total} questions are answered. Do not finish yet and do "
    "not reveal any level. Reply with done=false and the next question."
)


def next_question_message(number: int) -> str:
    """The per-turn instruction fixing this question's type, number and band."""
    step = QUESTION_PLAN[number - 1]
    return NEXT_QUESTION_MESSAGE.format(
        number=number, total=QUESTION_COUNT, band=step["band"], type=step["type"]
    )


def keep_going_message(asked: int) -> str:
    """Nudge for a model that answered done=true before all questions were asked."""
    return KEEP_GOING_MESSAGE.format(asked=asked, total=QUESTION_COUNT)


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
The target language is {sprache}. Conduct the ENTIRE conversation in {sprache}.

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
exactly. The learner's level is then how high up the ladder they still cope:
failing the A2 pair means A1, coping with the B2 pair means B1+.

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
- Address the learner with the informal second person, wherever {sprache}
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
  * gap fill: ONE short everyday sentence with a blank, plus three options
  * multiple choice: a question with three or four options labelled a), b), c), d).
    Say once that the learner may simply reply with the letter, and keep the
    options short and clearly distinct
  * error correction: one faulty sentence the learner has to rewrite correctly,
    no options
  * reading comprehension: one or two sentences of text, then a question on them
    with three options. Ask what the text MEANS, and make the answer depend on
    something only the language carries: a negation, a tense, a conditional, a
    connector, who a pronoun refers to, which of two events happened first.
    NEVER name a grammatical term and never ask which form a word is: the
    learner has to understand the sentence, not label it. Keep the options
    short, for instance yes, no, and the text does not say. Never ask a question
    whose answer is a phrase the text already contains, and never let the
    options be three different objects or topics.
    The shape to aim for: the text says something did not happen because a
    condition failed, and the question asks whether it happened
  * situation: one everyday situation in one sentence, then what the learner
    would say, with three options
  * free writing: two or three sentences of their own on an everyday topic, no
    options
- EXACTLY ONE option is correct, and every wrong option must be wrong for a
  reason you can grade: a wrong verb form, wrong word order, a wrong preposition,
  a word that does not fit the meaning, the wrong register. Options that all fit
  equally well test nothing. Before you send a task, check that a learner cannot
  defend a second option.
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
  {sprache} marks one, word order, a preposition, a connector, a relative
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
  option, or by elimination of nonsense. A learner who does not know {sprache}
  must have no way in.

DIFFICULTY LADDER
For each question you are told its band. Pick the point you test from that band.
These are categories, not {sprache} rules: use whatever realises them in
{sprache}, and skip a category the language does not have.
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
  line and labelled a), b), c). Keep that empty line before the first option
  even when the task already has a text and a question above it.

So a task with options looks like this:

<instruction>

<sentence with a blank, or the question>

a) <option>
b) <option>
c) <option>

A task without options is the instruction, an empty line, and the sentence.

NO HINTS IN BRACKETS. A blank is written as ___ and nothing else. Never put the
word class, the expected kind of word, the base form, a translation or any other
clue in brackets next to it, and never add such a hint anywhere else in the
task. The options carry everything the learner needs. Where there are no
options, the sentence alone has to do the work.

LEVEL ANCHORS
These describe the four outcomes and apply to {sprache} the same way they apply
to any other language.
- A1: isolated words and memorised phrases, present tense only, communication
  breaks down often. Copes with the A1 block but not the A2 block
- A2: simple main clauses on everyday topics, past tense attempted but often
  wrong, very limited vocabulary. Copes with the A2 block but not the B1 block
- B1: connected sentences with subordination, copes with familiar topics,
  errors do not block understanding. Copes with the B1 block but not the B2 block
- B1+: everything above B1, needs no language support. Copes with the B2 block
  too. Do not try to split this into B2, C1 or C2

OUTPUT FORMAT
Reply with ONLY a JSON object. No prose, no markdown fences, no explanation.
The line breaks required by TASK LAYOUT go inside the "message" string as \\n.

While the interview is still running, always use exactly these three keys:
{"done": false, "reaction": "<one short sentence in {sprache} about the answer you just read>", "message": "<your next question, written in {sprache}, without the reaction>"}

"reaction" is REQUIRED on every turn. The only turn where it may be an empty
string is your very first one, because there is no answer to react to yet.
Leaving it out later drops your reaction from the conversation entirely.

On the final turn, "level" must be exactly one of "A1", "A2", "B1", "B1+":
{"done": true, "message": "<two or three very simple sentences in {sprache}, encouraging in tone, naming one strength and one thing to work on. Simple enough for an A1 learner to read>", "level": "B1", "skill_scores": {"grammar": 60, "vocabulary": 55, "reading": 65, "writing": 50, "pragmatics": 60}}
"""


def render_system_prompt(template: str, language_name: str) -> str:
    """Substitute the target language into the admin-managed prompt template."""
    return template.replace(PROMPT_PLACEHOLDER, language_name)


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
