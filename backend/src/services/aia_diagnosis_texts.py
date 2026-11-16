"""The shipped texts of the language assessment: question set, prompts and examples."""

# Two exercise kinds: choice graded in code, free text typed.
CHOICE_TYPE = "choice"
FREE_TEXT_TYPE = "free text"


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


# Sent after an unreadable answer.
REPAIR_MESSAGE = (
    "Your last reply was not a JSON object, so it could not be used. Send the "
    "same turn again as ONLY the JSON object from the output format, with no "
    "text before or after it."
)


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
