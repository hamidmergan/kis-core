"""Fragen einmalig von der KI schreiben lassen, im Adminbereich.

Es gibt genau zwei Wege zu einem Fragen-Plan: von Hand tippen, oder hier einmal
erzeugen lassen und danach von Hand nachbessern. Beide enden in derselben Liste
und derselben Einstellung, es gibt keinen zweiten Testtyp.

Warum einmalig und nicht waehrend des Tests: ein Aufruf je Frage je Lernendem
lief gegen ein hochschulweit geteiltes Limit, niemand konnte die Fragen vorher
lesen, und der Lernende wartete vor jeder Frage auf das Modell. Einmal erzeugen
kostet EINEN Aufruf fuer den ganzen Kurs, die Verwaltung sieht das Ergebnis, und
jeder Test laeuft danach ohne Modell.

Der Auftrag traegt die Stufen-Leiter mit (Beschreibungen und Beispielsaetze aus
demselben Reiter), damit die Fragen zu genau der Skala passen, nach der spaeter
eingestuft wird.
"""

from src.services.aia_diagnosis_chat import (
    CHOICE_TYPE,
    FREE_TEXT_TYPE,
    MAX_ANSWERS,
    MAX_OPTIONS,
    MIN_OPTIONS,
    DiagnosisChatError,
    _loads_lenient,
)

# Die Plaetze in der Reihenfolge, in der erzeugt wird: von sehr leicht nach sehr
# anspruchsvoll, mit genug Plaetzen, die die KI spaeter beurteilt. Sie deckt sich
# Platz fuer Platz mit dem ausgelieferten Standardplan.
#
# Es gibt nur noch zwei Aufgabenarten, also traegt ein Platz zusaetzlich, WIE die
# Aufgabe aussehen soll ("shape"). Frueher hiessen die Arten selbst so ("reading
# comprehension", "situation") und der Auftrag brauchte nichts weiter. Die Arten
# waren im Code aber identisch, deshalb steht die Vielfalt jetzt hier, wo sie
# hingehoert: im Auftrag an das Modell, nicht in einem Dropdown, aus dem die
# Verwaltung dreimal dasselbe waehlen konnte.
#
# ``answers`` sagt, ob der Platz eine Loesung tragen soll. Ein Freitext MIT
# Loesung wird im Code bewertet (der alte Lueckentext), einer OHNE ist die
# Schreibprobe, aus der die Stufe entsteht.
GENERATION_SLOTS = [
    {"type": FREE_TEXT_TYPE, "answers": True,
     "shape": "one short everyday sentence with a blank ___ , solution is one word"},
    {"type": CHOICE_TYPE, "answers": False,
     "shape": "a plain grammar item, no lead-in text"},
    {"type": FREE_TEXT_TYPE, "answers": False,
     "shape": "one faulty sentence the learner rewrites correctly"},
    {"type": CHOICE_TYPE, "answers": False,
     "shape": "a plain grammar item, no lead-in text"},
    {"type": CHOICE_TYPE, "answers": False,
     "shape": "one or two sentences of reading, then a question on what they mean"},
    {"type": CHOICE_TYPE, "answers": False,
     "shape": "one everyday situation, then what the learner would say"},
    {"type": CHOICE_TYPE, "answers": False,
     "shape": "a grammar item on a paired connector or a complex word order"},
    {"type": FREE_TEXT_TYPE, "answers": False,
     "shape": "two or three sentences of their own on an everyday topic"},
    {"type": CHOICE_TYPE, "answers": False,
     "shape": "one or two sentences of demanding reading, then a question on what "
              "really happened, turning on a conditional or an irrealis"},
    {"type": FREE_TEXT_TYPE, "answers": False,
     "shape": "one long, demanding faulty sentence the learner rewrites correctly"},
    {"type": FREE_TEXT_TYPE, "answers": False,
     "shape": "three or four sentences taking a position on a question, with reasons"},
    {"type": CHOICE_TYPE, "answers": False,
     "shape": "a word-choice item in a formal register, where only one word fits"},
]

# Der Test ist deutsch, deshalb steht die Zielsprache im Auftrag fest.
GENERATION_LANGUAGE = "German"

_SYSTEM = (
    "You write placement-test questions for a German language centre. You answer "
    "with JSON only, never with prose around it."
)

_ORDER = """Write a complete placement test in {language}. Every question, every
answer option and every solution must be written in {language}.

THE LADDER
These describe a typical learner at each CEFR level:
{levels}

These are reference answers at each level:
{examples}

THE TASKS
Write exactly {count} questions, in this order, one per line below. Each line
names the task type, then what that entry MUST carry, then the shape to write.
None of it is optional:
{types}

The test rises from very easy at the first position to very demanding at the last,
so pitch each question by its position. Do NOT label a question with a level: the
level is read from the learner's answers later.

THE SHAPE
Answer with a JSON object {{"questions": [...]}} and nothing else. There are two
types of entry:

  choice
    {{"type": "choice", "text": "<the question, with any lead-in text>",
      "options": [{{"text": "<option>", "correct": true|false}}, ...]}}
    Give four options with EXACTLY ONE correct. Every other option must be a real,
    gradeable mistake, never a second right answer. Anything the task needs before
    the question, a short reading text or an everyday situation, goes into "text".

  free text WITH a solution
    {{"type": "free text", "text": "<sentence with ___ for the blank>",
      "answers": ["<accepted word>", "<other accepted spelling, optional>"]}}
    The learner TYPES the missing word, so give no options. The sentence must
    leave exactly one word that fits.

  free text WITHOUT a solution
    {{"type": "free text", "text": "<the task>"}}
    The learner writes their own sentences, so give no options and no "answers".
    This is the writing sample the level is read from.

Put the whole question into "text", including any reading passage. Never put the
answer options inside "text"."""


def _slot_requirement(slot: dict) -> str:
    """Was diese eine Nummer tragen muss, in Klammern hinter der Aufgabenart.

    Die Sammelregel unter THE SHAPE reicht nachweislich nicht: gemessen schrieb
    das Modell zwei Auswahl-Aufgaben hintereinander ohne Optionen, weil es die Art
    nur als Ueberschrift gelesen hat. An der Nummer selbst ist es nicht zu
    uebersehen.
    """
    if slot["type"] == CHOICE_TYPE:
        return "four options, exactly one correct"
    if slot["answers"]:
        return "the learner types the answer, so \"answers\" and no options"
    return "the learner writes freely, so no options and no answers"


def build_generation_messages(levels_block: str, examples_block: str,
                              slots: list[dict]) -> list[dict]:
    """Der eine Auftrag, aus dem der ganze Fragen-Plan entsteht.

    ``levels_block`` und ``examples_block`` kommen aus der Stufen-Leiter, in
    genau der Form, in der sie auch im Einstufungs-Prompt stehen. So schreibt das
    Modell die Fragen nach demselben Massstab, nach dem spaeter bewertet wird.

    Jeder Platz nennt neben der Aufgabenart auch seinen Charakter ("shape"). Mit
    nur zwei Arten waere der Auftrag sonst zwoelfmal fast derselbe Satz, und der
    Fragensatz wuerde eintoenig.
    """
    numbered = "\n".join(
        f"{i}. {slot['type']} ({_slot_requirement(slot)}) - {slot['shape']}"
        for i, slot in enumerate(slots, 1)
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _ORDER.format(
            language=GENERATION_LANGUAGE,
            levels=levels_block.strip(),
            examples=examples_block.strip(),
            count=len(slots),
            types=numbered,
        )},
    ]


_REPAIR = (
    "Your last answer could not be used. The problem: {reason}\n\n"
    "Send the WHOLE set again as one JSON object {{\"questions\": [...]}}, with that "
    "entry fixed and every other rule from the order still met. Fix exactly what is "
    "named above, do not rewrite the rest."
)


def build_repair_message(reason: str) -> str:
    """Das eine Nachfassen, mit dem konkreten Grund.

    Ein allgemeiner Reparaturtext half nicht: gemessen wiederholte das Modell
    denselben Fehler wortgleich, weil es gar nicht wusste, welche Frage woran
    gescheitert war.
    """
    return _REPAIR.format(reason=reason)


def _generated_options(raw, number: int) -> list[dict]:
    """Die Optionen einer erzeugten Auswahl-Frage, genau eine davon richtig.

    Strenger als der Speicherweg von Hand, der mehrere richtige zulaesst: eine
    Maschine, die zwei richtige Optionen schreibt, hat einen Ablenker erfunden,
    der selbst stimmt. Von Hand ist das eine Absicht, hier ist es ein Fehler.
    """
    if not isinstance(raw, list) or not (MIN_OPTIONS <= len(raw) <= MAX_OPTIONS):
        raise DiagnosisChatError(f"Question {number}: needs {MIN_OPTIONS}..{MAX_OPTIONS} options")
    options: list[dict] = []
    correct = 0
    for opt in raw:
        if not isinstance(opt, dict):
            raise DiagnosisChatError(f"Question {number}: option is not an object")
        text = opt.get("text")
        if not isinstance(text, str) or not text.strip():
            raise DiagnosisChatError(f"Question {number}: option without text")
        flag = bool(opt.get("correct"))
        correct += flag
        options.append({"text": text.strip(), "correct": flag})
    if correct != 1:
        raise DiagnosisChatError(
            f"Question {number}: needs exactly one correct option, got {correct}"
        )
    return options


def _generated_answers(raw, number: int) -> list[str]:
    """Der Loesungsschluessel einer erzeugten Tipp-Frage."""
    if not isinstance(raw, list) or not (1 <= len(raw) <= MAX_ANSWERS):
        raise DiagnosisChatError(f"Question {number}: needs 1..{MAX_ANSWERS} answers")
    answers: list[str] = []
    for answer in raw:
        if not isinstance(answer, str) or not answer.strip():
            raise DiagnosisChatError(f"Question {number}: empty answer")
        answers.append(answer.strip())
    return answers


def parse_generated_plan(raw: str, slots: list[dict]) -> list[dict]:
    """Die Antwort des Modells als fertiger Fragen-Plan, oder ein Fehler.

    Streng geprueft, weil das Ergebnis unveraendert gespeichert wird: die Anzahl
    und die Reihenfolge der Aufgabenarten muessen stimmen, jede Frage braucht
    ihren Text, jede Auswahl-Frage genau eine richtige Option und jeder Platz mit
    Loesung seinen Loesungsschluessel. Ein Fehler loest den einen Reparaturversuch
    des Aufrufers aus, statt der Verwaltung eine halbe Liste hinzulegen.

    Ein ueberzaehliges Feld an einer Schreibprobe faellt still weg. Das ist kein
    Qualitaetsproblem, nur ein Modell, das eine Zeile zu gut gemeint hat.
    """
    parsed = _loads_lenient(raw)
    if not isinstance(parsed, dict):
        raise DiagnosisChatError("Response must be a JSON object")
    questions = parsed.get("questions")
    if not isinstance(questions, list):
        raise DiagnosisChatError("Missing \"questions\" array")
    if len(questions) != len(slots):
        raise DiagnosisChatError(
            f"Expected {len(slots)} questions, got {len(questions)}"
        )

    plan: list[dict] = []
    for number, (item, slot) in enumerate(zip(questions, slots), 1):
        qtype = slot["type"]
        if not isinstance(item, dict):
            raise DiagnosisChatError(f"Question {number}: not an object")
        if item.get("type") != qtype:
            raise DiagnosisChatError(
                f"Question {number}: expected type {qtype!r}, got {item.get('type')!r}"
            )
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise DiagnosisChatError(f"Question {number}: missing question text")

        step = {"type": qtype, "text": text.strip()}
        if qtype == CHOICE_TYPE:
            step["options"] = _generated_options(item.get("options"), number)
        elif slot["answers"]:
            step["answers"] = _generated_answers(item.get("answers"), number)
        plan.append(step)
    return plan
