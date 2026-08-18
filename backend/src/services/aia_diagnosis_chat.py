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

from src.services.aia_level_ladder import LEVELS, build_levels_block


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
# demanding (last), so the model varies difficulty by where a slot sits. The plan
# keeps at least MIN_FREE_TEXT_QUESTIONS slots the AI judges, since free writing
# is what the level actually rests on. The admin owns the plan. Index 0 is Q1.
#
# JEDE Frage im Plan ist ausgeschrieben, entweder von Hand oder einmalig von der
# KI im Adminbereich. Es gibt keinen Plan mehr, der nur Typen nennt und dessen
# Fragen das Modell waehrend des Tests erfindet: das kostete einen Aufruf je Frage
# je Lernendem, niemand konnte die Fragen vorher pruefen, und der Lernende wartete
# vor jeder Frage. Der ausgelieferte Plan
# steht weiter unten als DEFAULT_GERMAN_QUESTION_PLAN.

# ZWEI Aufgabenarten, nicht mehr sechs. Frueher standen sechs im Dropdown (gap
# fill, multiple choice, error correction, reading comprehension, situation, free
# writing), aber im Code gab es immer nur diese zwei Auslieferungsformen. Drei der
# sechs waren Wort fuer Wort dasselbe Multiple Choice und unterschieden sich nur
# darin, was VOR der Frage stand, und das steht ohnehin im frei getippten
# Fragetext. Wer eine Lesefrage oder eine Alltagssituation will, schreibt sie
# einfach hinein.
#
# CHOICE_TYPE: Antwortoptionen a), b), c), d). Im Code bewertet.
# FREE_TEXT_TYPE: kein Anklicken, der Lernende tippt selbst.
CHOICE_TYPE = "choice"
FREE_TEXT_TYPE = "free text"
VALID_QUESTION_TYPES = {CHOICE_TYPE, FREE_TEXT_TYPE}

# Die sechs alten Namen bleiben lesbar, damit ein gespeicherter Plan (und jeder
# Test, der gerade laeuft) unveraendert weiterlaeuft. Sie werden beim Einlesen auf
# die zwei Arten abgebildet und danach nie wieder geschrieben. Der Lueckentext
# wird Freitext MIT Loesung, die anderen beiden Freitext OHNE, genau wie vorher.
LEGACY_TYPE_ALIASES = {
    "multiple choice": CHOICE_TYPE,
    "reading comprehension": CHOICE_TYPE,
    "situation": CHOICE_TYPE,
    "gap fill": FREE_TEXT_TYPE,
    "error correction": FREE_TEXT_TYPE,
    "free writing": FREE_TEXT_TYPE,
}

# Bei Auswahl-Fragen bestimmt der Server, WO die richtige Option steht, und zieht
# die Stelle jedes Mal neu. Modelle setzen die richtige Antwort stark bevorzugt
# auf a), was den Test kaputt wirken laesst ("die Antwort ist immer a"); eine
# feste Rotation half, war aber selbst vorhersagbar (man konnte nach Position
# raten, ohne zu lesen), also wird gewuerfelt. Freitext hat nichts zu mischen.

# Every plan must carry at least this many free-text questions the AI judges,
# meaning free text WITHOUT a solution key. A choice question only shows what a
# learner RECOGNISES, and a free text with a solution key is a one-word gap, so
# neither is production the model can read a level off. Without this floor an
# all-recognition plan would let the model hand out C1/C2 on nothing. Two gives a
# second signal without overloading a weak learner (who can still skip), and the
# shipped plan carries four, so the default is never affected.
MIN_FREE_TEXT_QUESTIONS = 2
# Bounds for an authored option set. Four is the shipped shape, but an expert may
# use fewer or a couple more; a single option is not a choice and a runaway count
# is a paste accident.
MIN_OPTIONS = 2
MAX_OPTIONS = 8
# Bounds for a free text's answer key. One accepted answer is the normal case;
# the extra room is for the spellings that are genuinely just as right
# ("Straße" / "Strasse"), not for a list long enough to accept anything.
MAX_ANSWERS = 8
# Bis zu dieser Laenge ist eine Loesung ein Wort oder eine Wendung, also bekommt
# der Lernende ein einzeiliges Feld. Ist die Loesung laenger, ist ein ganzer Satz
# gemeint (etwa ein richtig geschriebener Fehlersatz) und das grosse Feld passt.
# Frueher hing die Feldgroesse am Typ 'gap fill'; den gibt es nicht mehr, und die
# Loesung selbst sagt es genauso gut.
SHORT_ANSWER_MAX_CHARS = 40
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
# (the Einstufungs-Regeln field), {levels} with the per-level descriptions from the
# Stufen-Leiter, {examples} with the per-band calibration example list. All three
# are VISIBLE in the prompt itself, so nothing is merged in secretly. If a custom
# prompt drops a placeholder, that block is appended at the end.
GRADING_PLACEHOLDER = "{grading}"
LEVELS_PLACEHOLDER = "{levels}"
EXAMPLES_PLACEHOLDER = "{examples}"

# The bands that carry a calibration example, one per CEFR level. Each is a
# reference answer the final grading call compares free-text answers against, and
# the adaptive chat reuses the same samples to calibrate how it writes per level.
# Reihenfolge und Umfang kommen aus der Stufen-Leiter, damit Beschreibungen und
# Beispiele nie auseinanderlaufen.
EXAMPLE_LEVELS = list(LEVELS)

# Soft UI limit for the answer length. The hard backend cap stays
# MAX_MESSAGE_CHARS; this one only drives the counter and maxlength in the client.
DEFAULT_ANSWER_MAX_CHARS = MAX_MESSAGE_CHARS

def canonical_type(raw_type) -> str | None:
    """Die Aufgabenart in ihrer heutigen Form, oder None wenn unbekannt.

    Nimmt die zwei heutigen Namen und die sechs alten. So oeffnet ein Plan, der
    vor der Zusammenlegung gespeichert wurde, ohne Umbau und ohne Datenwanderung:
    gelesen wird umbenannt, geschrieben wird nur noch neu.
    """
    if not isinstance(raw_type, str):
        return None
    if raw_type in VALID_QUESTION_TYPES:
        return raw_type
    return LEGACY_TYPE_ALIASES.get(raw_type)


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


def _parse_answers(raw_answers) -> list[str] | None:
    """Validate an authored answer key for a typed question, or None when unusable.

    The key is a plain list of accepted answers, ``["gehe"]`` in the common case.
    There is no correct flag: everything in the list IS correct, which is what an
    author expects from a field called "Lösung". One to MAX_ANSWERS entries, each a
    non-empty string. Returns the stripped answers, or None so the caller can
    revert the whole plan, exactly like a broken option set does.
    """
    if not isinstance(raw_answers, list) or not (1 <= len(raw_answers) <= MAX_ANSWERS):
        return None
    cleaned: list[str] = []
    for answer in raw_answers:
        if not isinstance(answer, str) or not answer.strip():
            return None
        cleaned.append(answer.strip())
    return cleaned


def _legacy_answers_from_options(raw_options) -> list[str] | None:
    """Answer key recovered from a stored gap fill that still carries options.

    Gap fill used to be an option type, so the oldest plans hold four options with
    a correct flag. Reading the correct ones as the answer key keeps such a plan
    working word for word instead of silently dropping it back to the shipped
    default. Returns None when the option set itself is broken, so the caller
    reverts as it always did.
    """
    cleaned = _parse_options(raw_options)
    if cleaned is None:
        return None
    return [opt["text"] for opt in cleaned if opt["correct"]]


def _parse_step(item) -> dict | None:
    """Eine gespeicherte Zeile in ihrer geprueften Form, oder None wenn unbrauchbar.

    Felder:
      * ``"type"``   ``choice`` oder ``free text``, Pflicht. Ein alter Name aus der
        Zeit der sechs Arten wird hier umbenannt. Eine Frage traegt KEINE
        CEFR-Stufe: das Modell stuft aus den Antworten ein, nicht anhand eines
        Etiketts an der Frage.
      * ``"text"``   der Fragetext, wortwoertlich so gezeigt.
      * ``"options"`` (nur Auswahl) die Antwortoptionen mit ``correct``-Flag. Im
        Code bewertet, also ohne Modellaufruf.
      * ``"answers"`` (nur Freitext, freiwillig) die akzeptierten Antworten.
        Stehen sie da, bewertet der Code; fehlen sie, liest die KI am Ende. Ein
        Lueckentext aus der Zeit vor den Tipp-Antworten traegt noch ``"options"``,
        dessen richtige werden zum Loesungsschluessel.
    Ein altes ``"band"``, ein ``"example"`` und Optionen an einem Freitext werden
    ignoriert statt abgelehnt, damit ein altes Feld nicht stoert.
    """
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
    """True, wenn die Zeile im Test allein tragfaehig ist.

    Fertig heisst: ein Fragetext ist da, und eine Auswahl hat ihre Optionen. Ein
    Freitext braucht nur den Text: seine Loesung ist freiwillig, ohne sie
    beurteilt der Abschluss-Aufruf die Antwort.

    Frueher durfte eine Zeile halb sein und das Modell schrieb die Frage waehrend
    des Tests. Diesen Weg gibt es nicht mehr, deshalb ist Unvollstaendigkeit jetzt
    ein Fehler statt ein Modus.
    """
    if not (step.get("text") or "").strip():
        return False
    if step.get("type") == CHOICE_TYPE and not step.get("options"):
        return False
    return True


def parse_question_plan(raw: str) -> list[dict]:
    """Der gespeicherte Fragen-Plan, sonst der ausgelieferte deutsche Standard.

    Eine kaputte ODER unfertige Zeile setzt den ganzen Plan auf den Standard
    zurueck (bestehende Philosophie: der Test laeuft immer auf einem brauchbaren
    Plan). Unfertig kann heute nur noch Altbestand sein, denn der Speicherweg
    lehnt so etwas ab; ohne diesen Rueckfall stuende sonst eine Frage ohne Text im
    Test.
    """
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


# Der ausgelieferte deutsche Fragensatz und damit der Standard fuer JEDEN Test,
# solange die Verwaltung nichts eigenes gespeichert hat. Vollstaendig ausgeschrieben:
# echter deutscher Text und Optionen mit correct-Flag, also laeuft der Normalfall
# sofort und mit NULL Modellaufrufen. Der Test ist deutsch, deshalb gibt es genau
# diesen einen Standard und keine Verzweigung nach Sprache mehr. Die Verwaltung darf
# alles davon aendern oder ersetzen, von Hand oder einmalig von der KI erzeugt.
# Die Fragen stehen von sehr leicht nach sehr anspruchsvoll, so deckt der Test die
# ganze Spanne ab; die Stufe liest das Modell aus den Antworten, die Fragen selbst
# tragen keine. Jede Auswahl-Frage hat genau eine richtige Option und lauter
# Ablenker, die ein echter, bewertbarer Fehler sind.
DEFAULT_GERMAN_QUESTION_PLAN = [
    {
        "type": FREE_TEXT_TYPE,
        "text": "Setze das passende Wort ein.\n\nIch ___ jeden Tag zur Arbeit.",
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
    """True iff every item in the admin JSON is well-formed.

    The save path uses this to reject a typo with a 400, rather than storing
    something the runtime then silently reverts to a default. Mirrors
    :func:`parse_question_plan`: the type must be known (both of today's names and
    the six old ones), an option set must pass ``_parse_options``, an answer key
    must pass ``_parse_answers``, and text must be a string. A legacy ``band``
    field is ignored, and so is a legacy option set on an old gap fill, which the
    runtime converts to an answer key instead of rejecting.
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
        if canonical_type(item.get("type")) is None:
            return False
        if item.get("text") is not None and not isinstance(item.get("text"), str):
            return False
        if _parse_step(item) is None:
            return False
    return True


def count_judged_questions(plan: list[dict]) -> int:
    """Wie viele Zeilen eines eingelesenen Plans die KI beurteilt.

    Das sind die Freitext-Zeilen OHNE Loesung. Eine Auswahl bewertet der Code, ein
    Freitext MIT Loesung ebenfalls; nur wo nichts zum Abgleichen steht, muss der
    Abschluss-Aufruf die Sprache selbst lesen, und genau daran haengt die Stufe.
    """
    return sum(
        1 for step in plan
        if step.get("type") == FREE_TEXT_TYPE and not step.get("answers")
    )


def question_plan_has_enough_free_text(raw: str) -> bool:
    """True iff the admin plan carries at least MIN_FREE_TEXT_QUESTIONS questions
    the AI judges (free text without a solution key).

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
    steps = [step for step in (_parse_step(item) for item in data) if step is not None]
    return count_judged_questions(steps) >= MIN_FREE_TEXT_QUESTIONS


def first_incomplete_question(raw: str) -> int | None:
    """Die 1-basierte Nummer der ersten unfertigen Zeile, sonst None.

    Fertig heisst: ein Fragetext ist immer da, und eine Auswahl hat ihre Optionen.
    Ein Freitext braucht nur den Text, seine Loesung ist freiwillig.

    Save-Path-Politik wie :func:`question_plan_has_enough_free_text`, absichtlich
    getrennt von :func:`question_plan_is_valid` (Struktur). Frueher war eine halbe
    Zeile erlaubt und das Modell hat die Frage waehrend des Tests erzeugt; diesen
    Weg gibt es nicht mehr, also muss die Luecke beim Speichern auffallen.
    """
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


def answer_key(step: dict) -> list[str]:
    """The accepted answers of a free text that carries a solution, in order.

    Never sent to the client: the learner types, so knowing the key would give the
    answer away outright, unlike an option list that has to be shown anyway.
    """
    return list(step.get("answers", []))


# Punctuation a learner may leave at the end of a typed answer. Ending a one-word
# answer with a full stop is a habit, not a language mistake, and marking it wrong
# would be graded typing rather than graded language.
_TRAILING_PUNCTUATION = ".,;:!?…"


def normalize_typed_answer(value: str) -> str:
    """Fold a typed answer down to what actually carries meaning.

    Dropped: outer whitespace, doubled inner whitespace, trailing punctuation and
    capitalisation. Kept: every letter as written, so "gehe" never matches "geht"
    and a missing umlaut stays a mistake. ``lower`` rather than ``casefold`` on
    purpose, since casefold would quietly make "Straße" equal "strasse" and that
    is the author's call to make in the answer key, not ours.
    """
    folded = " ".join(value.split()).rstrip(_TRAILING_PUNCTUATION).strip()
    return folded.lower()


def grade_typed(step: dict, answer: str) -> bool:
    """Deterministic grade for a free text whose author set a solution.

    Correct iff the typed answer folds onto one of the accepted answers. A skipped
    question arrives as an empty string and is never correct. Nothing is guessed
    here: a near miss is simply wrong, since the author decides which spellings
    count by listing them.
    """
    key = {normalize_typed_answer(a) for a in answer_key(step)}
    if not key:
        return False
    return normalize_typed_answer(answer) in key


def question_mode(step: dict) -> str:
    """Wie eine Zeile ausgeliefert und bewertet wird.

    * manual_options: Auswahl. Sofort ausgeliefert, im Code bewertet.
    * manual_typed: Freitext MIT Loesung. Sofort ausgeliefert, im Code gegen den
      Loesungsschluessel bewertet, also ohne Modellaufruf.
    * manual_text: Freitext OHNE Loesung. Sofort ausgeliefert, vom
      Abschluss-Aufruf beurteilt.

    Entscheidend ist nicht mehr die Aufgabenart, sondern ob eine Loesung dasteht:
    seit es nur noch zwei Arten gibt, ist genau das der Schalter zwischen "der
    Code weiss die Antwort" und "die KI muss lesen". Jede Zeile im laufenden Plan
    ist vollstaendig (:func:`step_is_complete`), es fehlt also nichts. Ein vierter
    Modus 'auto', bei dem das Modell die Frage waehrend des Tests schrieb, ist
    entfallen.
    """
    if step.get("type") == CHOICE_TYPE:
        return "manual_options"
    if step.get("answers"):
        return "manual_typed"
    return "manual_text"


def _shuffle(values: list[str], rng=None) -> list[str]:
    """A shuffled copy of ``values``. Display order carries no signal, so the
    correct answer is never learnable from position. ``rng`` is injectable so a
    test can pin the order."""
    order = list(values)
    (rng or random).shuffle(order)
    return order


def wants_short_box(step: dict) -> bool:
    """True, wenn der Lernende hier ein einzeiliges Feld bekommt.

    Nur bei Freitext mit Loesung, und nur wenn jede zugelassene Loesung kurz ist
    (SHORT_ANSWER_MAX_CHARS). Ein Lueckensatz mit der Loesung "gehe" ist damit
    einzeilig, ein Fehlersatz, dessen Loesung der ganze richtige Satz ist,
    bekommt das grosse Feld. Frueher hing das am Typ 'gap fill'.
    """
    answers = answer_key(step)
    return bool(answers) and all(len(a) <= SHORT_ANSWER_MAX_CHARS for a in answers)


def manual_question_payload(step: dict, rng=None) -> dict:
    """Client payload for an expert-authored question, with no model involved.

    The message is the authored question text. Choice questions also carry the
    shuffled option values (never the correct flags) and a ``multi`` flag so the
    client picks radio vs checkbox. A free text with a short solution carries
    ``short`` so the client offers a one-line box instead of the big one meant for
    whole sentences; the answer key itself stays here. Everything else carries
    only the message.
    """
    payload = {"done": False, "message": step["text"]}
    if step.get("type") == CHOICE_TYPE and step.get("options"):
        payload["options"] = _shuffle(option_values(step), rng)
        payload["multi"] = is_multi_correct(step)
    if wants_short_box(step):
        payload["short"] = True
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


# Der Standard, wie er bis 2026-08 ausgeliefert wurde, mit der Stufen-Liste am
# Ende. Steht nur noch hier, um ihn beim Lesen als "nicht gesetzt" zu erkennen:
# wer den Text damals angefasst und wieder zurueckgesetzt hat, hat ihn gespeichert
# und bekaeme sonst die Liste doppelt (einmal hier, einmal ueber {levels}). Nicht
# loeschen, siehe aia_level_ladder.resolve_prompt_setting.
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

# Editable grading rules, kept out of the main prompt so a language expert can
# tune HOW the level is decided in one focused field. Injected at the
# {grading} placeholder. Language-agnostic: it describes the CEFR scale, not
# one language's forms.
#
# Beschreibt nur noch das VERFAHREN. Wie eine Stufe aussieht, steht in der
# Stufen-Leiter (aia_level_ladder) und wird ueber {levels} eingesetzt, damit ein
# Sprachexperte sie an EINER Stelle auf Deutsch pflegt statt hier auf Englisch.
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

# Shipped calibration examples: TWO per band, one sentence per LINE (kein "--"
# mehr, das Admin-Feld verspricht eine Zeile je Satz und soll auch so aussehen;
# example_items versteht beides weiter). The two
# contexts are the SAME across all bands (line 1 is always the cinema/weekend
# situation, line 2 is always the work situation), so the model can compare how
# the SAME idea is expressed as the level rises. That contrast is what makes the
# examples calibrate well. An answer of similar quality to a band's examples
# points to that level. Editable per level by an expert.
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
    main_prompt: str,
    grading_rules: str,
    descriptions: dict,
    examples: dict,
    language_name: str,
) -> str:
    """Build the full diagnosis system prompt.

    Three visible placeholders are filled: {grading} with the grading procedure,
    {levels} with the per-level descriptions from the Stufen-Leiter and
    {examples} with the per-band example list. All three are just editable
    content, so the reader sees the whole structure in the prompt. If a
    customised prompt dropped a placeholder, that block is appended under its own
    header so the model never loses it. The {language} substitution then runs
    over the whole.
    """
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
