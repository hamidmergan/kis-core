"""Grammatik-Übung aus Quelltext (tool='grammatik', mode='source').

Ein Generier-Call liefert das Musterpaar und N Satzpaare. Der Aufgabentyp steuert
den Call nur über zwei Textfelder aus dem Katalog (``instruction`` und ``rule``),
deshalb kostet ein neuer Aufgabentyp hier keine Zeile Code.

Wichtig für den Zweck des Tools: die Sätze werden NEU aus dem Quellinhalt gebaut,
nicht aus einem Arbeitsblatt übernommen. Deshalb funktioniert das Tool mit jeder
Quelle, auch mit einem Mathe-Skript.
"""

import json

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json, _language_label

from src.features.ai_assistant.tasks.language_training._attribution import (
    PAGE_RULE,
    attach_chips_cited,
)
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.services.aia_grammar_check import normalize, overlap_ratio


_SHAPE = (
    'Respond ONLY with a JSON object. Every exercise carries its "kind", its "page" '
    'and a short "explanation" naming the form that decides it:\n'
    '{"title": "Short topic title", "exercises": [\n'
    '  {"kind": "transform", "before": "Sentence in the original form", '
    '"after": "The same sentence transformed", "explanation": "...", "page": 12},\n'
    '  {"kind": "cloze", "sentence": "Sentence with the target form replaced by ___", '
    '"answer": "What belongs in the gap", "explanation": "...", "page": 12},\n'
    '  {"kind": "statement", "statement": "A sentence that either shows the target '
    'form correctly or gets it wrong", "answer": true, "explanation": "...", '
    '"page": 12},\n'
    '  {"kind": "choice", "task": "The form the learner has to produce", '
    '"sentence": "The statement to transform", '
    '"options": ["...", "...", "...", "..."], "correct_idx": 0, '
    '"explanation": "...", "page": 12}\n'
    ']}\n'
)

# Feste Beschriftung für Richtig/Falsch statt einer vom Modell erfundenen: es schrieb
# sonst mal "Wahr", mal "richtig", und die Ansicht zeigt die Optionen unverändert an.
_VERDICT_LABELS = {"de": ("Richtig", "Falsch"), "en": ("True", "False")}

# Fragezeichen quer über Schriftsysteme. Ein 'before' mit Fragezeichen ist keine
# Aussage und damit nicht umformbar, egal in welcher Sprache.
_QUESTION_MARKS = "?？؟;՞।"

# Die Anweisung an den Lernenden. Sie nennt die Zielform bewusst NICHT, sie zeigt
# sie: darunter steht das Musterpaar. Wortlaut vom Sprachenzentrum, wie auf dem
# Papier-Arbeitsblatt. Früher hing sie am Katalogeintrag, aber sie war dort für
# jedes Thema dieselbe.
_INSTRUCTION = {
    "de": "Bitte transformiere nach folgendem Muster:",
    "en": "Please transform according to the following pattern:",
}

# Unter dieser Quote gilt ein Durchlauf als misslungen: lieber ein fehlgeschlagenes
# Set als eine Übung, in der die Hälfte der Aufgaben unlösbar ist.
_MIN_USABLE_RATIO = 0.5

# Die vier Darreichungsformen, in dieser Reihenfolge reihum verteilt. Das Format war
# früher eine Wahl im Dialog, ist aber kein Thema, sondern eine Darreichungsform. Ein
# Lernender profitiert mehr davon, dieselbe Form auf vier Arten zu üben als zehnmal
# auf eine.
#
# Die Reihenfolge ist eine Entscheidung: geht die Anzahl nicht glatt auf, bekommen die
# vorderen Formate einen mehr. Vorne steht deshalb die Umformung, die das eigentliche
# Können prüft, hinten das Ankreuzen, das am meisten hilft.
KINDS = ("transform", "cloze", "statement", "choice")

# Vier Optionen beim Ankreuzen. Weniger sieht nach einem Fehler aus, mehr passt nicht
# mehr auf die Karte.
_OPTION_COUNT = 4

# Ab dieser Wortüberdeckung mit der Lösung gilt eine falsche Option als Formvariante
# und nicht als andere Aussage. Das ist der Inhalt-gegen-Form-Filter: vier
# Passiv-Varianten teilen fast alle Wörter, vier verschiedene Gerichte teilen nur das
# "und". Kommt ohne Wortlisten aus und gilt damit für jede Sprache.
_MIN_OPTION_OVERLAP = 0.5

# So wird eine Lücke geschrieben. Ein einzelnes Zeichen wäre im Fließtext nicht zu
# erkennen, drei Unterstriche sind es.
GAP = "___"


def item_plan(count: int) -> list[str]:
    """Welche Aufgabe welches Format bekommt, reihum über :data:`KINDS`.

    Als ZAHL im Prompt und nicht als Absichtserklärung. Erfahrung aus dem
    Grammatik-Quiz und dem Hörverstehen: "stelle abwechslungsreiche Aufgaben" wirkt
    nicht, "genau 4 Aufgaben der Art X" wirkt.
    """
    return [KINDS[i % len(KINDS)] for i in range(max(0, count))]


def generate_grammar_from_source(
    client, model,
    ctx: QuelleContext,
    grammar_type: dict,
    count: int,
    locale: str = "de",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
) -> tuple[list[dict], str, dict]:
    """Returns (items, title, header). ``header`` holds instruction + example pair.

    Empty items mean the run is unusable and the caller fails the set.
    """
    language = _language_label(locale)
    target_form = grammar_type["label"]
    shipped_example = grammar_type["example"]
    plan = item_plan(count)
    prompt = (
        _build_prompt(grammar_type, target_form, shipped_example, plan, language)
        + adaptive_suffix + title_avoidance + coverage
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Write the output in {language}.\n\nSources:\n\n{ctx.context}"},
    ]
    # Same temperature as the MC tools: enough wording variety, still JSON-safe. The real
    # variation across runs comes from the rotating page subset in build_source_context.
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.6)
    data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))

    exercises = list(data.get("exercises") or [])[:count]
    items, claims = _build_items(exercises, locale, shipped_example)

    # The model likes to slip back into comprehension questions ("Was bedeutet X?"),
    # which cannot be transformed and leave the learner stuck. Too many of those and
    # the whole run is thrown away rather than shipped half broken.
    wanted = min(count, len(exercises)) or count
    if len(items) < max(1, int(wanted * _MIN_USABLE_RATIO)):
        logger.warning(
            "KI Tutor: grammar run discarded, only {}/{} sentences were usable",
            len(items), wanted,
        )
        return [], "", {}

    # Nav-only chip per sentence, taking the page the model itself named and falling back
    # to search and then to the section. Not the plain post-hoc search the other tools use:
    # these sentences are invented and then transformed, so searching them back finds
    # nothing for roughly half of them and the set ends up half cited, half not.
    attach_chips_cited(items, claims, ctx)

    title = (data.get("title") or "").strip() or grammar_type["label"]
    # Kein Set-Kopf mehr: ein gemischtes Set hat kein gemeinsames Muster, das über
    # allem stehen könnte. Das Muster hängt an der Aufgabe, die eines braucht.
    return items, title, {}


def _build_prompt(grammar_type: dict, target_form: str, example: dict,
                  plan: list, language: str) -> str:
    # The worked pair is given as a SHAPE TO COPY, not only as a rule. Rules alone
    # get ignored by the chat model, which then falls back to what it does most
    # often and returns comprehension questions instead of transformable sentences.
    shape = (
        "SHAPE TO COPY. Every exercise looks exactly like this pair:\n"
        f'  before: "{example["before"]}"\n'
        f'  after:  "{example["after"]}"\n\n'
        "NOT like these, they are all wrong here:\n"
        '  "Was bedeutet wissenschaftliches Arbeiten?"  (a question, cannot be transformed)\n'
        '  "Nennen Sie drei Beispiele."                 (an instruction, not a statement)\n'
        '  "Wissenschaftliches Arbeiten"                (not a sentence)\n\n'
    )
    return (
        f"You build a grammar drill from the given source text. "
        f"Write ALL sentences in {language}, regardless of the source-text language.\n\n"
        # The learner-facing instruction is deliberately NOT sent: it only says "follow
        # the pattern below" and names no form. The topic label does.
        f"Target form: {target_form}\n"
        f"Transformation rule: {grammar_type['rule']}\n\n"
        + shape +
        f"Write exactly {len(plan)} exercises: {_plan_sentence(plan)}. The SAME target "
        "form throughout, only the way the learner answers changes.\n\n"
        "What each kind is:\n"
        "- transform: the learner rewrites 'before' into 'after' themselves.\n"
        f"- cloze: take a sentence that ALREADY shows the target form and replace exactly "
        f"the part that carries it with {GAP}. 'answer' is what belongs in the gap and "
        "must not appear anywhere else in the sentence, otherwise it can be read off.\n"
        "- statement: a sentence that either shows the target form correctly or gets it "
        "wrong. 'answer' is true when it is correct. About half of them are false, and a "
        "false one is wrong in exactly ONE detail of the form.\n"
        "- choice: four options that differ ONLY in form, same words, same content. "
        "Exactly one is correct, the other three are mistakes a learner actually makes. "
        "'correct_idx' counts from 0.\n\n"
        "How to build the sentences:\n"
        "- Take the FACTS, terms and topics from the source text and write NEW, simple "
        "sentences about them. Never copy a sentence from the source verbatim.\n"
        "- Never copy exercises that may already be in the source text. The source supplies "
        "subject matter, not exercises.\n"
        "- Every sentence is a STATEMENT. Never a question, never an instruction to the "
        "learner, never a bare phrase.\n"
        "- Every 'before' MUST be a valid input for the transformation rule above. "
        "If the rule needs a modal verb, every sentence contains one.\n"
        "- 'after' is the single expected solution, correct and complete, and it must "
        "differ from 'before'.\n"
        # Deliberately NO length or complexity rule here. How hard a sentence is comes
        # from exactly one place, the learner's CEFR level (build_adaptive_tool_suffix).
        # A cap here would contradict that block at B2 and above, where it says not to
        # simplify. This line is only about shape: one sentence, not a paragraph.
        "- Every sentence is exactly ONE sentence.\n"
        "- Do NOT use personal names. Write 'die Dozentin', 'das Team', 'according to the source' "
        "instead, matching the output language.\n"
        + PAGE_RULE + "\n"
        + _SHAPE
    )


def _plan_sentence(plan: list[str]) -> str:
    """Die Mischung als Zahlensatz. Gezählt statt beschrieben, weil nur das wirkt."""
    counts: dict[str, int] = {}
    for kind in plan:
        counts[kind] = counts.get(kind, 0) + 1
    return ", ".join(f'{n} of kind "{kind}"' for kind, n in counts.items())


def is_usable_pair(before: str, after: str) -> bool:
    """Whether a generated pair is actually solvable by a learner.

    Deliberately language-agnostic: no word lists, only shape. A question or an
    unchanged sentence has no correct transformation, so shipping it would leave
    the learner with an exercise nobody can answer.
    """
    if not before or not after:
        return False
    if before[-1] in _QUESTION_MARKS or after[-1] in _QUESTION_MARKS:
        return False
    if normalize(before) == normalize(after):
        return False
    # A single word (or none) is a heading, not a sentence to transform.
    return len(before.split()) >= 3


def is_usable_statement(text: str, verdict) -> bool:
    """Ob eine Richtig/Falsch-Aussage beurteilbar ist.

    Eine Frage hat keinen Wahrheitswert, und ohne ausdrückliches ja oder nein weiss
    niemand, was die richtige Antwort sein soll. ``bool`` ist in Python ein ``int``,
    deshalb wird auf den Typ geprüft und nicht auf Wahrheit.
    """
    text = (text or "").strip()
    if not text or not isinstance(verdict, bool):
        return False
    if text[-1] in _QUESTION_MARKS:
        return False
    # Zwei Wörter sind eine Überschrift, keine Aussage.
    return len(text.split()) >= 3


def is_usable_cloze(sentence: str, answer: str) -> bool:
    """Ob ein Lückensatz lösbar ist.

    Der wichtigste Fall ist der letzte: steht die Lösung sonst noch im Satz, liest der
    Lernende sie ab. Das Modell macht das gern, wenn das gesuchte Wort im Satz ein
    zweites Mal vorkommt.
    """
    sentence = (sentence or "").strip()
    answer = (answer or "").strip()
    if not sentence or not answer:
        return False
    if GAP not in sentence:
        return False
    # Nur eine Lücke und sonst nichts ist kein Satz, sondern ein leeres Feld.
    if len(sentence.replace(GAP, " ").split()) < 3:
        return False
    return normalize(answer) not in normalize(sentence.replace(GAP, " ")).split(
        "  ") and normalize(answer) not in normalize(sentence.replace(GAP, ""))


def is_usable_choice(task: str, sentence: str, options: list, correct_idx) -> bool:
    """Ob eine Ankreuz-Aufgabe wirklich eine Form übt.

    Sprach-unabhängig: keine Wortlisten, nur Form und Wortüberdeckung. Die Überdeckung
    trennt eine Formaufgabe von einer Inhaltsfrage, und das ist der Fehler, für den
    dieser Filter überhaupt gebaut wurde.
    """
    if not task or not sentence:
        return False
    # Ein oder zwei Wörter sind eine Überschrift, kein Satz zum Umformen.
    if len(sentence.split()) < 3:
        return False
    if not options or len(options) != _OPTION_COUNT:
        return False
    # bool ist in Python ein int, und True hiesse still und leise Position 1.
    if not isinstance(correct_idx, int) or isinstance(correct_idx, bool):
        return False
    if not 0 <= correct_idx < len(options):
        return False

    normalized = [normalize(opt) for opt in options]
    if not all(normalized):
        return False
    # Zwei Optionen, die sich nur in Gross- und Kleinschreibung unterscheiden, sind
    # dieselbe Antwort zweimal. Der Lernende kann recht haben und falsch liegen.
    if len(set(normalized)) != len(normalized):
        return False
    # Eine Option, die den Satz wiederholt, formt nichts um.
    if normalize(sentence) in normalized:
        return False

    correct = options[correct_idx]
    return all(
        overlap_ratio(opt, correct) >= _MIN_OPTION_OVERLAP
        for i, opt in enumerate(options) if i != correct_idx
    )


def _build_items(exercises: list[dict], locale: str,
                 example: dict) -> tuple[list[dict], list[str]]:
    """Item-Zeilen plus der Text, über den die Quelle zugeordnet wird.

    Alle vier Formate teilen eine Zeilenform: Aufgabentext in ``front``, erwartete
    Antwort in ``back``. Die Ansicht unterscheidet sie daran, ob ``options`` gesetzt
    ist, nicht an einem eigenen Feld. Was durch seinen Filter fällt, kommt nicht ins
    Set: eine unlösbare Aufgabe ist schlimmer als eine fehlende.
    """
    yes, no = _VERDICT_LABELS.get(locale, _VERDICT_LABELS["en"])
    items, claims = [], []
    for ex in exercises:
        kind = (ex.get("kind") or "transform").strip().lower()
        built = _build_one(ex, kind, yes, no, example)
        if built is None:
            logger.debug("KI Tutor: Grammatik-Aufgabe verworfen ({}): {!r}", kind, ex)
            continue
        item, claim = built
        item["explanation"] = (ex.get("explanation") or "").strip() or None
        # Welchen nummerierten Abschnitt das Modell benutzt haben will. Wird nicht
        # gespeichert, der Aufrufer prüft damit die Abdeckung.
        item["_section"] = ex.get("section")
        # Die Seite, aus der das Modell den Stoff genommen haben will. Liest und
        # entfernt attach_chips_cited, nachdem es sie gegen die gesehenen Seiten prüft.
        item["_page"] = ex.get("page")
        items.append(item)
        claims.append(claim)
    return items, claims


def _build_one(ex: dict, kind: str, yes: str, no: str, example: dict):
    """Eine Zeile für ein Format, oder ``None``, wenn sie durch den Filter fällt.

    Der zurückgegebene Text ist das, woran die Quelle hängt. Es ist überall der Satz,
    der den Inhalt trägt, nie die feste Beschriftung: "Richtig" steht in keiner Quelle
    und würde die Suche verwässern.
    """
    if kind == "transform":
        before = (ex.get("before") or "").strip()
        after = (ex.get("after") or "").strip()
        if not is_usable_pair(before, after):
            return None
        # Nur die Umformung braucht ein Muster, sonst weiss der Lernende nicht wohin.
        # Bei den anderen Formaten wäre es Ballast.
        return {"front": before, "back": after,
                "extras": {"pattern_front": example["before"],
                           "pattern_back": example["after"]}}, after

    if kind == "cloze":
        sentence = (ex.get("sentence") or "").strip()
        answer = (ex.get("answer") or "").strip()
        if not is_usable_cloze(sentence, answer):
            return None
        return {"front": sentence, "back": answer}, sentence.replace(GAP, answer)

    if kind == "statement":
        text = (ex.get("statement") or "").strip()
        verdict = ex.get("answer")
        if not is_usable_statement(text, verdict):
            return None
        return {"front": text, "back": yes if verdict else no,
                "options": [yes, no], "correct_idx": 0 if verdict else 1}, text

    if kind == "choice":
        task = (ex.get("task") or "").strip()
        sentence = (ex.get("sentence") or "").strip()
        options = [str(o).strip() for o in (ex.get("options") or [])]
        idx = ex.get("correct_idx")
        if not is_usable_choice(task, sentence, options, idx):
            return None
        # Leerzeile zwischen Anweisung und Satz: auf einer Zeile ist nicht klar,
        # auf welchen Satz sich die Aufgabe bezieht.
        return {"front": f"**{task}**\n\n{sentence}", "back": options[idx],
                "options": options, "correct_idx": idx}, options[idx]

    # Eine Art, die es nicht gibt. Zu raten wäre schlimmer als wegzulassen.
    return None
