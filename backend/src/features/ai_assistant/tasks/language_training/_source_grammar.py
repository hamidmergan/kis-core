"""Grammatik-Übung aus Quelltext (tool='grammatik', mode='source').

Ein Generier-Call liefert das Musterpaar und N Satzpaare. Der Aufgabentyp steuert
den Call nur über zwei Textfelder aus dem Katalog (``instruction`` und ``rule``),
deshalb kostet ein neuer Aufgabentyp hier keine Zeile Code.

Wichtig für den Zweck des Tools: die Sätze werden NEU aus dem Quellinhalt gebaut,
nicht aus einem Arbeitsblatt übernommen. Deshalb funktioniert das Tool mit jeder
Quelle, auch mit einem Mathe-Skript.
"""

import json
import re

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json

from src.features.ai_assistant.tasks.language_training._attribution import (
    PAGE_RULE,
    attach_chips_cited,
)
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._plan import (
    plan_sentence,
    room_left,
    still_missing,
)
from src.services.aia_grammar_check import normalize, overlap_ratio
from src.services.aia_grammar_formats import KINDS
from src.services.llm_context_healing import create_with_shrink


_SHAPE = (
    'Respond ONLY with a JSON object. Every exercise carries its "kind", its "page" '
    'and a short "explanation" naming the form that decides it:\n'
    '{"title": "Short topic title", "exercises": [\n'
    '  {"kind": "transform", "before": "Sentence in the original form", '
    '"after": "The same sentence transformed", "also_ok": ["Another wording that is '
    'just as correct"], "explanation": "...", "page": 12},\n'
    '  {"kind": "cloze", "sentence": "A complete, correct sentence showing the target '
    'form, with NO gap in it", "form_span": "The part of that sentence which carries '
    'the form, copied out of it character for character", '
    '"options": ["...", "...", "...", "..."], '
    '"correct_idx": 0, "explanation": "...", "page": 12},\n'
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

# Die Anweisung an den Lernenden, je Format eine.
#
# Sie steht AN der Aufgabe und nicht mehr über dem Set: ein gemischtes Set hat keine
# gemeinsame Anweisung, denn Umformen, Ergänzen und Ankreuzen sind verschiedene
# Tätigkeiten. Ohne sie sieht der Lernende einen nackten Satz und weiss nicht, was er
# tun soll, auch nicht mit Eingabefeld davor. Genau so gemeldet am 2026-08-05.
#
# Anders als früher nennt sie die Zielform ausdrücklich. Der alte Wortlaut ("nach
# folgendem Muster") zeigte auf ein Musterpaar über dem Set, das es nicht mehr gibt.
# Der Verweis auf das Muster ist zurück und steht beim Umformen MITTEN in der Zeile.
# Er wurde eine Zeit lang hinten angehängt, und genau das kam am 2026-08-12 zurück:
# "Setze den Satz ins Relativsatz, nach dem Beispiel." Ein Komma-Anhängsel hinter einem
# frei formulierten Satz liest sich immer schief, und bei "Bilde den Satz nach der
# tekamolo-Regel" stünde zweimal "nach". Wer den Satz schreibt, schreibt den Verweis
# mit oder lässt ihn weg.
#
# Der Themenname steht hinter einem Doppelpunkt und nicht hinter einer Präposition.
# Beugen kann die Schablone ihn nicht, also lässt sie es: "ins {form}" verlangt ein
# Geschlecht, einen Fall und eine Zahl, die sie nicht kennt, und traf damit nur
# sächliche Einzahlwörter. Vier Meldungen vom 2026-08-12 zeigen, dass auch die richtige
# Beugung nicht reicht ("Setze den Satz ins tekamolo" bleibt falsch, weil tekamolo eine
# Stellungsregel ist und kein Behälter). Ein Doppelpunkt stimmt für jeden Namen und in
# jeder Sprache. Der schön formulierte Satz kommt vom Modell, siehe ``eigene`` in
# :func:`task_line`.
_TASK_LINES = {
    "de": {
        "transform": "Forme den Satz nach dem Beispiel um. Zielform: {form}.",
        "cloze": "Ergänze das fehlende Wort. Zielform: {form}.",
        "statement": "Ist der Satz korrekt? Zielform: {form}.",
        "choice": "Welcher Satz ist korrekt? Zielform: {form}.",
    },
    "en": {
        "transform": "Rewrite the sentence following the example. Target form: {form}.",
        "cloze": "Fill in the missing word. Target form: {form}.",
        "statement": "Is the sentence correct? Target form: {form}.",
        "choice": "Which sentence is correct? Target form: {form}.",
    },
}


def task_line(kind: str, locale: str, target_form: str, eigene: dict | None = None) -> str:
    """Die Anweisung für ein Format, in der Sprache des Sets.

    Sie wird immer gesetzt, auch wenn das Modell eine eigene liefert: eine fehlende
    Anweisung macht die Aufgabe unlösbar, das darf nicht vom Modell abhängen.

    ``eigene`` sind die beim Ausarbeiten des Themas formulierten Zeilen. Sie haben
    Vorrang, weil nur sie den Themennamen beugen können: "Forme den Satz in einen
    Relativsatz um." liest sich wie von einer Lehrkraft geschrieben, die Schablone
    nennt ihn bloss ("Zielform: Relativsatz."). Beides ist richtig, aber nur eines ist
    schön.

    Themen von vor diesem Feld bekommen ihre Zeilen beim nächsten Benutzen nachgereicht,
    siehe :func:`src.services.aia_grammar_topic.derive_task_lines`. Die Schablone greift
    nur noch, solange das nicht geklappt hat.

    Was hier ankommt, geht unverändert an den Lernenden. Der Verweis auf das Muster
    wurde eine Zeit lang hinten angehängt, wenn er fehlte, und ergab genau die am
    2026-08-12 gemeldete Zeile: "..., nach dem Beispiel." Er gehört in den Satz, also
    schreibt ihn, wer den Satz schreibt.
    """
    fertig = (eigene or {}).get(kind)
    if fertig and fertig.strip():
        return fertig.strip()
    lines = _TASK_LINES.get(locale, _TASK_LINES["en"])
    return lines.get(kind, lines["transform"]).replace("{form}", target_form)


# Unter dieser Quote gilt ein Durchlauf als misslungen: lieber ein fehlgeschlagenes
# Set als eine Übung, in der die Hälfte der Aufgaben unlösbar ist.
_MIN_USABLE_RATIO = 0.5

# Bis zu drei Wuerfe, damit die bestellte Anzahl zusammenkommt. Die Filter werfen
# weg, und wer zehn Aufgaben bestellt, will zehn. Mehr als drei bringt nichts: wer
# dreimal nichts Brauchbares liefert, liefert es beim vierten Mal auch nicht.
_MAX_ATTEMPTS = 3

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

# Höchstens so viele Wörter darf der Formträger haben, den der Code aus dem Satz
# schneidet. Vier, weil es echte Formen aus vier Wörtern gibt ("hätte geschrieben werden
# können"). Das ist nur die äussere Grenze gegen eine Lücke, die den Satz schluckt. Die
# Regel, die eine zu grosse Lücke wirklich erkennt, steht in :func:`is_usable_cloze`:
# kein Wort darf in allen vier Optionen stehen.
_MAX_SPAN_WORDS = 4

# Ab dieser Länge gilt ein Wort des Themennamens als Fachwort, das in einem Übungssatz
# nichts zu suchen hat. Siehe :func:`names_the_form`.
_MIN_TERM_CHARS = 6


def item_plan(count: int, kinds=None) -> list[str]:
    """Welche Aufgabe welches Format bekommt, reihum über die gewählten Formate.

    Als ZAHL im Prompt und nicht als Absichtserklärung. Erfahrung aus dem
    Grammatik-Quiz und dem Hörverstehen: "stelle abwechslungsreiche Aufgaben" wirkt
    nicht, "genau 4 Aufgaben der Art X" wirkt.

    ``kinds`` ist die Auswahl des Lernenden. Leer oder ``None`` heisst gemischt, also
    alle vier. Reihum heisst auch hier: geht die Anzahl nicht glatt auf, bekommen die
    vorderen Formate einen mehr.
    """
    verfuegbar = list(kinds) if kinds else list(KINDS)
    return [verfuegbar[i % len(verfuegbar)] for i in range(max(0, count))]


def generate_grammar_from_source(
    client, model,
    ctx: QuelleContext,
    grammar_type: dict,
    count: int,
    locale: str = "de",
    # Nur der Vollstaendigkeit halber entgegengenommen: die Uebungssaetze folgen der
    # Sprache der Quelle, nicht der des Kursraums. Die Anweisungszeile und die
    # Richtig/Falsch-Beschriftung haengen weiter an `locale`, das ist Geruest fuer den
    # Lernenden und gehoert in die Unterrichtssprache.
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
    # Die gewaehlten Aufgabenformate. Leer oder None heisst gemischt, also alle vier.
    # Steuert die Verteilung UND filtert: eine Aufgabe einer abgewaehlten Art wird bei
    # jedem Wurf verworfen, auch beim letzten.
    kinds: list[str] | None = None,
) -> tuple[list[dict], str, dict]:
    """Returns (items, title, header). ``header`` holds instruction + example pair.

    Empty items mean the run is unusable and the caller fails the set.
    """
    target_form = grammar_type["label"]
    shipped_example = grammar_type["example"]
    plan = item_plan(count, kinds)
    # Bewusst KEINE Zielsprache: die Uebungssaetze bleiben in der Sprache der Quelle.
    # Grammatik ist das einzige Werkzeug, bei dem die Sprache nicht das Mittel ist,
    # sondern der Lernstoff. Geuebt wird an den Saetzen, die im Dokument stehen, und
    # eine uebersetzte Passiv-Uebung uebt nichts: entweder erfindet das Modell
    # deutsche Saetze zu einem englischen Text, oder es schreibt englische Saetze zu
    # einem Thema wie "Konjunktiv II", das es auf Englisch nicht gibt.
    #
    # Die Sprache muss dafuer nirgends erkannt werden: das Modell hat den Quelltext
    # vor sich und behaelt einfach dessen Sprache bei.
    user_msg = f"Sources:\n\n{ctx.context}"

    def messages_for(wanted: list[str]) -> list[dict]:
        prompt = (
            _build_prompt(grammar_type, target_form, shipped_example, wanted)
            + adaptive_suffix + title_avoidance + coverage
        )
        return [{"role": "system", "content": prompt},
                {"role": "user", "content": user_msg}]
    # Ein zweiter Wurf, wenn der erste zu wenig Brauchbares liefert. Die Filter werfen
    # weg, und ohne Nachschlag kam bei zehn bestellten Aufgaben ein Set mit sieben
    # heraus. Genau ein Nachschlag: wer zweimal hintereinander nichts Brauchbares
    # liefert, liefert es beim dritten Mal erfahrungsgemäss auch nicht.
    items: list[dict] = []
    claims: list[str] = []
    seen: set = set()
    seen_exercises = 0
    data: dict = {}
    for attempt in range(_MAX_ATTEMPTS):
        # Der Nachschlag fragt NUR nach dem, was noch fehlt. Ohne das kippt die
        # Mischung: das Modell liefert beim zweiten Wurf am liebsten Ankreuz-Aufgaben,
        # und bei zehn bestellten kamen fuenf davon heraus statt der geplanten zwei.
        wanted = still_missing(plan, items)
        if not wanted:
            break
        last_try = attempt == _MAX_ATTEMPTS - 1
        if last_try:
            # Im letzten Wurf zaehlt die Anzahl mehr als die Mischung, also wird nicht
            # noch einmal nach der Art gefragt, die gerade zweimal am Filter gescheitert
            # ist. Gemessen an Set 5599: dreimal "1 of kind choice" bestellt, dreimal
            # dieselbe unbrauchbare Aufgabe bekommen, vier von fuenf Aufgaben im Set.
            #
            # Der Rueckgriff bleibt dabei INNERHALB der gewaehlten Formate. Sonst
            # bekaeme der Lernende im letzten Wurf genau das Format, das er
            # weggeklickt hat.
            wanted = _fallback_kinds(items, wanted, kinds)
        # Same temperature as the MC tools: enough wording variety, still JSON-safe. The
        # real variation comes from the context sweep in build_source_context, and any
        # repeat that still slips through is dropped afterwards by _dedup.
        response = create_with_shrink(client, endpoint="grammatik", model=model, messages=messages_for(wanted), temperature=0.6)
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
        exercises = list(data.get("exercises") or [])[:count]
        seen_exercises += len(exercises)
        fresh, fresh_claims = _build_items(exercises, locale, shipped_example, target_form,
                                           grammar_type.get("task_lines"))
        # Bis zum letzten Wurf gilt der Deckel je Format: was ueber den Plan
        # hinausgeht, wird nicht genommen, sonst kippt die Mischung schon im ersten
        # Wurf. Im LETZTEN Wurf zaehlt die Anzahl mehr als die Mischung, denn wer zehn
        # bestellt hat, will zehn.
        room = {} if last_try else room_left(plan, items)
        for item, claim in zip(fresh, fresh_claims):
            # Schluessel aus Aufgabentext UND Loesung. Seit die "welcher Satz ist
            # korrekt?"-Bauart ihren Satz nicht mehr wiederholt, sehen zwei solche
            # Aufgaben vorn gleich aus und nur die Loesung unterscheidet sie.
            key = (normalize(item["front"]), normalize(item["back"]))
            if key in seen:
                continue
            kind = item.get("_kind")
            # Eine abgewaehlte Art wird IMMER verworfen, auch im letzten Wurf. Dort
            # faellt der Deckel je Format, damit die bestellte Anzahl zusammenkommt,
            # aber ein abgehaktes Kaestchen ist keine Vorliebe bei der Mischung
            # sondern ein Ausschluss. Ohne diese Sperre kam bei "nur Umformen" eine
            # Richtig/Falsch-Aufgabe heraus, nachgestellt am 2026-08-10.
            if kinds and kind not in kinds:
                continue
            if not last_try:
                if room.get(kind, 0) <= 0:
                    continue
                room[kind] -= 1
            seen.add(key)
            items.append(item)
            claims.append(claim)
        if len(items) >= count:
            break
        logger.info("KI Tutor: Grammatik-Wurf {} ergab {}/{} Aufgaben",
                    attempt + 1, len(items), count)
    items, claims = items[:count], claims[:count]

    # The model likes to slip back into comprehension questions ("Was bedeutet X?"),
    # which cannot be transformed and leave the learner stuck. Too many of those and
    # the whole run is thrown away rather than shipped half broken.
    wanted = min(count, seen_exercises) or count
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

    # ``_kind`` bleibt an der Aufgabe. Es traegt die Darreichungsform in den Vorrat,
    # und nur dort steht sie ueber diesen Lauf hinaus. Der Aufrufer entfernt es, sobald
    # eingelagert ist.

    title = (data.get("title") or "").strip() or grammar_type["label"]
    # Kein Set-Kopf mehr: ein gemischtes Set hat kein gemeinsames Muster, das über
    # allem stehen könnte. Das Muster hängt an der Aufgabe, die eines braucht.
    return items, title, {}


def _fallback_kinds(have: list[dict], missing: list[str], kinds=None) -> list[str]:
    """Welche Arten der letzte Wurf bestellt: die, die schon geliefert haben.

    Was noch fehlt, ist genau das, was der Filter zweimal verworfen hat. Ein drittes Mal
    danach zu fragen bringt dasselbe zurueck, und der Satz bleibt zu kurz. Eine Art, die
    in diesem Set schon eine brauchbare Aufgabe hergegeben hat, gibt eher eine zweite her.

    ``kinds`` ist die Auswahl des Lernenden und begrenzt, worauf zurueckgegriffen werden
    darf. Leer oder ``None`` heisst gemischt, also alle vier.

    Hat noch keine geliefert, bleibt es bei den fehlenden: dann ist nicht die Art das
    Problem, sondern der Wurf, und irgendetwas muss bestellt werden.
    """
    erlaubt = [k for k in KINDS if not kinds or k in kinds]
    geklappt = [kind for kind in erlaubt if any(i.get("_kind") == kind for i in have)]
    if not geklappt:
        return missing
    return [geklappt[i % len(geklappt)] for i in range(len(missing))]


def _build_prompt(grammar_type: dict, target_form: str, example: dict,
                  plan: list) -> str:
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
        # Für das Ankreuzen ein eigenes Beispiel, weil die Regel "nur die Form ändert
        # sich" allein nicht wirkt. Gemessen am 2026-08-05: das Modell tauschte im
        # Falschantwort das Subjekt aus ("Die Studierenden werden geschrieben."), und
        # der Wortüberdeckungs-Filter warf jede Ankreuz-Aufgabe raus. Ein Beispiel
        # wirkt, wo eine Regel nicht wirkt, dieselbe Lehre wie überall in diesem Werkzeug.
        "OPTIONS TO COPY, for kind \"choice\". Note how all four say the SAME thing "
        "about the SAME people and differ only in the verb form:\n"
        '  "Der Bericht wird vom Team geschrieben."      <- the correct one\n'
        '  "Der Bericht ist vom Team geschrieben."\n'
        '  "Der Bericht wird vom Team schreiben."\n'
        '  "Der Bericht wurde vom Team geschrieben."\n\n'
        "NOT like this, it changes who does what instead of the form:\n"
        '  "Das Team wird geschrieben."\n\n'
    )
    return (
        "You build a grammar drill from the given source text. "
        "Write ALL exercise sentences in the SAME language as the source text. "
        "Do NOT translate them into any other language.\n\n"
        # The learner-facing instruction is deliberately NOT sent: it only says "follow
        # the pattern below" and names no form. The topic label does.
        f"Target form: {target_form}\n"
        f"Transformation rule: {grammar_type['rule']}\n\n"
        + shape +
        f"Write exactly {len(plan)} exercises: {plan_sentence(plan)}. The SAME target "
        "form throughout, only the way the learner answers changes.\n\n"
        "What each kind is:\n"
        "- transform: the learner rewrites 'before' into 'after' themselves.\n"
        # Die Luecke schneidet der Code. Frueher lieferte das Modell sie fertig, und
        # vier der sechs Meldungen vom 2026-08-12 entstanden genau dabei: es nahm den
        # halben Satz heraus, liess ein Wort doppelt stehen oder setzte zwei Luecken.
        # Seit es den vollen Satz plus den Ausschnitt liefert, ergibt die gefuellte
        # Luecke wieder genau diesen Satz, und keiner der vier Fehler ist formulierbar.
        "- cloze: write a COMPLETE, correct sentence that shows the target form, with "
        "NO gap in it. 'form_span' is the part of that sentence which carries the form, "
        "copied out of it character for character, at most three words. The software "
        "cuts the gap, not you. Whatever stands in 'form_span' is what the learner "
        "fills in, so the sentence has to read correctly with it:\n"
        '    sentence "Die Messwerte werden vom Server gespeichert.", '
        'form_span "werden"\n'
        "  Give four short options, all different, one of them exactly 'form_span', the "
        "other three forms a learner actually confuses. 'correct_idx' points at "
        "'form_span' and counts from 0.\n"
        "- statement: a sentence that either shows the target form correctly or gets it "
        "wrong. 'answer' is true when it is correct. About half of them are false, and a "
        "false one is wrong in exactly ONE detail of the form. It is a sentence that "
        "USES the form, never a claim ABOUT grammar. Wrong here, it states a rule "
        'instead of practising it: "Das Verb steht im Relativsatz immer am Ende."\n'
        "- choice: four options that differ ONLY in form, same words, same content. "
        "Every option is a COMPLETE SENTENCE, never a single word and never a bare "
        "verb form, because the learner picks a finished sentence. Exactly one is "
        "correct, the other three are mistakes a learner actually makes. "
        "'correct_idx' counts from 0.\n\n"
        "How to build the sentences:\n"
        "- Take the FACTS, terms and topics from the source text and write NEW, simple "
        "sentences about them. Never copy a sentence from the source verbatim.\n"
        "- Never copy exercises that may already be in the source text. The source supplies "
        "subject matter, not exercises.\n"
        # Die Wurzel von Meldung 4 und 6 vom 2026-08-12. Die Quellen des
        # Sprachenzentrums sind Grammatik-Arbeitsblaetter, dort SIND die Fakten Regeln,
        # und "nimm die Fakten aus dem Text" ergab Saetze ueber die Grammatik statt in
        # ihr. Ein Satz, der die Zielform beim Namen nennt, fliegt jetzt auch im Code
        # heraus, siehe :func:`names_the_form`.
        "- Never NAME the target form inside a sentence. The exercises practise the "
        "form, they never talk about it. If the source text is itself about grammar, "
        "take the subject matter from its example sentences (fire safety, rescue "
        "systems, measurements) and never its rules.\n"
        "- Every sentence is a STATEMENT. Never a question, never an instruction to the "
        "learner, never a bare phrase.\n"
        "- Every 'before' MUST be a valid input for the transformation rule above. "
        "If the rule needs a modal verb, every sentence contains one.\n"
        "- 'after' is the expected solution, correct and complete, and it must "
        "differ from 'before'.\n"
        # Die Antwort wird beim Pruefen nur noch verglichen, kein Modell urteilt mehr
        # ueber sie. Deshalb muss JEDE gueltige Fassung schon hier dastehen, sonst
        # bekommt ein Lernender fuer eine richtige Antwort ein Rot.
        #
        # Als REGEL formuliert liefert das Modell durchgehend eine leere Liste, gemessen
        # am 2026-08-09 ueber ein ganzes Set. Erst das ausgearbeitete Beispiel fuellt sie.
        # Dieselbe Lehre wie beim Aufgabenformat weiter oben.
        "- 'also_ok' lists OTHER wordings of the same transformation that are just as "
        "correct, up to two. Work them out for every sentence before you move on:\n"
        '    before "Ich habe keine Zeit.", after "Ich hätte Zeit.", '
        'also_ok ["Ich würde Zeit haben."]\n'
        '    before "Der Server speichert die Messwerte.", '
        'after "Die Messwerte werden vom Server gespeichert.", '
        'also_ok ["Die Messwerte werden gespeichert."]\n'
        "  Typical cases are a different word order, an equally correct alternative "
        "form, and an optional part left out. The learner's answer is marked by "
        "comparing it against 'after' and this list and nothing else, so a valid "
        "wording missing here is marked as a mistake. An empty list is the rare "
        "exception, only when no other correct wording exists at all.\n"
        # Deliberately NO length or complexity rule here. How hard a sentence is comes
        # from exactly one place, the learner's CEFR level (build_adaptive_tool_suffix).
        # A cap here would contradict that block at B2 and above, where it says not to
        # simplify. This line is only about shape: one sentence, not a paragraph.
        "- Every sentence is exactly ONE sentence.\n"
        "- Do NOT use personal names. Write 'die Dozentin', 'das Team', 'according to the source' "
        "instead, matching the output language.\n"
        # Der Musterssatz steht jetzt AN der Aufgabe, mit seiner Loesung darunter.
        # Kommt er selbst als Aufgabe vor, muss der Lernende nur abschreiben.
        "- The worked pair above is a SHAPE, never an exercise. Never reuse its "
        "sentence, not as 'before', not in a gap sentence, not as an option.\n"
        + PAGE_RULE + "\n"
        + _SHAPE
    )


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


def cut_gap(sentence: str, form_span: str) -> str | None:
    """Der Satz mit der Lücke an der Stelle des Formträgers, oder ``None``.

    Hier liegt der Unterschied zu allem vor dem 2026-08-12: die Lücke schneidet der
    CODE. Vorher lieferte das Modell den Lückensatz fertig und entschied selbst, wie
    viel es herausnimmt. Vier der sechs Meldungen von diesem Tag entstanden genau dabei,
    unter anderem "Die Familienmitglieder ___ am Wochenende treffen." mit der Lösung
    "müssen getroffen werden", wo hinten "treffen" stehen blieb.

    Seither gilt eine Zusage, die keine Prüfung mehr braucht: die gefüllte Lücke ergibt
    wieder genau den Ausgangssatz. Ein übriges Wort, ein doppeltes Wort, eine zweite
    Lücke sind damit nicht mehr ausdrückbar.

    ``None`` heisst, daraus lässt sich keine Lücke schneiden: der Ausschnitt steht nicht
    wortwörtlich im Satz, er steht mehrfach darin, er ist zu lang, oder es bliebe kein
    Satz übrig. Verglichen wird an Wortgrenzen, sonst träfe "der" auch in "oder" und
    kaum ein Ausschnitt wäre eindeutig.
    """
    sentence = (sentence or "").strip()
    span = (form_span or "").strip()
    if not sentence or not span:
        return None
    # In eine Lücke gehört eine Form, nicht der halbe Satz. Die Wortgrenze steht bei
    # :data:`_MAX_SPAN_WORDS`, dort steht auch, warum sie nur die äussere Schranke ist.
    if len(span.split()) > _MAX_SPAN_WORDS:
        return None
    # Mehrfach vorhanden heisst nicht eindeutig: ersetzt würden zwei Stellen, und zwei
    # Lücken mit einer Lösung waren Meldung 6 vom 2026-08-12.
    stelle = re.compile(rf"(?<!\w){re.escape(span)}(?!\w)")
    if len(stelle.findall(sentence)) != 1:
        return None
    gapped = stelle.sub(GAP, sentence, count=1)
    # Nur eine Lücke und sonst nichts ist kein Satz, sondern ein leeres Feld.
    if len(gapped.replace(GAP, " ").split()) < 3:
        return None
    return gapped


def names_the_form(text: str, target_form: str) -> bool:
    """Ob der Satz die Zielform beim Namen nennt.

    Ein Regelsatz nennt sie ("Das Verb steht im Relativsatz immer am Ende."), ein
    Übungssatz nicht ("Die Messwerte werden vom Server gespeichert."). Genau daran sind
    die Meldungen 4 und 6 vom 2026-08-12 zu erkennen, und zwar ohne Wortliste: geprüft
    wird gegen den Themennamen aus dem Katalog, und der ist Daten und keine Sprachregel.
    Damit gilt die Prüfung für jedes Thema und jede Sprache.

    Nur Wörter ab :data:`_MIN_TERM_CHARS` Zeichen zählen. Fachwörter sind lang
    ("Relativsatz", "Konjunktiv", "Passiv"), Alltagswörter kurz, und ein Thema, das
    "haben und sein" heisst, würde sonst jeden eigenen Übungssatz verwerfen. Greift die
    Prüfung für so ein Thema nicht, ist das der bessere Ausfall: lieber kein Schutz für
    ein Thema als kein Set.

    Verglichen werden WÖRTER und keine Zeichenfolgen, sonst träfe "Passiv" in "Kompass".
    """
    woerter = set(normalize(text).split())
    if not woerter:
        return False
    return any(begriff in woerter
               for begriff in normalize(target_form).split()
               if len(begriff) >= _MIN_TERM_CHARS)


def is_usable_cloze(sentence: str, form_span: str, options: list, correct_idx) -> bool:
    """Ob aus Satz und Formträger eine lösbare Lücke wird.

    Deutlich kürzer als vor dem 2026-08-12, weil :func:`cut_gap` die Lücke schneidet:
    dass sie überhaupt im Satz steht, dass es genau eine ist, dass sie nicht hinten
    dranhängt und dass die Lösung nicht sonst noch im Satz vorkommt, kann seither nicht
    mehr schiefgehen. Es bleibt die Frage, ob sich schneiden lässt, und die vier Optionen.

    Vier Optionen zum Anklicken, keine freie Eingabe. Als Freitext war die Aufgabe
    zu schwer und zu offen: bei "Die Arbeit wird von der Dozentin ___." kann man
    vieles schreiben, und der Lernende raet, statt eine Form zu entscheiden.

    Der Wortüberdeckungs-Filter des Ankreuzens gilt hier ausdrücklich NICHT. In eine
    Lücke gehört ein Wort, keine Satzvariante, und vier Wortformen teilen sich naturgemäss
    keine Wörter.
    """
    if cut_gap(sentence, form_span) is None:
        return False

    if not options or len(options) != _OPTION_COUNT:
        return False
    if not isinstance(correct_idx, int) or isinstance(correct_idx, bool):
        return False
    if not 0 <= correct_idx < len(options):
        return False
    normalized = [normalize(opt) for opt in options]
    if not all(normalized):
        return False
    # Zweimal dieselbe Antwort: der Lernende kann recht haben und falsch liegen.
    if len(set(normalized)) != len(normalized):
        return False
    # Kein Wort darf in ALLEN vier Optionen stehen. Steht eines überall, ist es nicht die
    # geübte Form, sondern Zusammenhang, und der gehört in den Satz und nicht in die
    # Lücke. Das waren die Meldungen 2 und 3 vom 2026-08-12: die Lücke schluckte das
    # Nomen ("einen Handfeuerlöscher", "ein sicheres Rettungssystem"), und alle vier
    # Optionen wiederholten es brav mit.
    #
    # Diese Regel und nicht :data:`_MAX_SPAN_WORDS` ist der eigentliche Schutz gegen eine
    # zu grosse Lücke: "ein sicheres Rettungssystem" sind drei Wörter und wären unter
    # jeder vernünftigen Wortgrenze durchgekommen. Vier Formen einer Verbgruppe teilen
    # sich dagegen zwar Wörter, aber keines steht in allen vier.
    #
    # Sprach-unabhängig, weil nur Wörter verglichen werden. Beim Ankreuzen gilt genau das
    # Gegenteil (siehe :data:`_MIN_OPTION_OVERLAP`), denn dort sind die Optionen ganze
    # Sätze und müssen sich fast alles teilen.
    if set.intersection(*(set(n.split()) for n in normalized)):
        return False
    # Die markierte Option muss der Formträger sein, sonst zeigt die Ansicht das eine
    # an und die Prüfung erwartet das andere.
    return normalized[correct_idx] == normalize(form_span)


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
    # Der Satz darf als RICHTIGE Option dastehen: das Modell baut die Aufgabe oft als
    # "welche Form ist richtig?", und dann ist der Satz selbst die Loesung. Als FALSCHE
    # Option bleibt er verboten, denn dann hiesse die Aufgabe "streiche das, was du
    # ohnehin liest". Bis zum 2026-08-05 fielen dadurch reihenweise Aufgaben durch und
    # die Sets kamen zu kurz heraus.
    if normalize(sentence) in normalized and normalized[correct_idx] != normalize(sentence):
        return False

    correct = options[correct_idx]
    return all(
        overlap_ratio(opt, correct) >= _MIN_OPTION_OVERLAP
        for i, opt in enumerate(options) if i != correct_idx
    )


def _build_items(exercises: list[dict], locale: str, example: dict,
                 target_form: str,
                 eigene_zeilen: dict | None = None) -> tuple[list[dict], list[str]]:
    """Item-Zeilen plus der Text, über den die Quelle zugeordnet wird.

    Alle vier Formate teilen eine Zeilenform: Aufgabentext in ``front``, erwartete
    Antwort in ``back``. Die Ansicht unterscheidet sie daran, ob ``options`` gesetzt
    ist, nicht an einem eigenen Feld. Was durch seinen Filter fällt, kommt nicht ins
    Set: eine unlösbare Aufgabe ist schlimmer als eine fehlende.
    """
    yes, no = _VERDICT_LABELS.get(locale, _VERDICT_LABELS["en"])
    # Der Musterssatz und seine Loesung. Kommt einer davon als Aufgabe zurueck, steht
    # die Antwort direkt darunter. Der Prompt verbietet es, das Modell haelt sich aber
    # nicht daran, also steht die Sperre auch im Code.
    banned = {normalize(example.get("before") or ""), normalize(example.get("after") or "")}
    banned.discard("")
    items, claims = [], []
    for ex in exercises:
        kind = (ex.get("kind") or "transform").strip().lower()
        built = _build_one(ex, kind, yes, no, example)
        if built is None:
            logger.debug("KI Tutor: Grammatik-Aufgabe verworfen ({}): {!r}", kind, ex)
            continue
        item, claim = built
        if _repeats_example(item["front"], banned):
            logger.debug("KI Tutor: Grammatik-Aufgabe wiederholt das Muster: {!r}",
                         item["front"])
            continue
        # Ein Satz, der die Zielform beim Namen nennt, ist eine Aussage ÜBER die
        # Grammatik und keine Übung IN ihr. Gemeldet am 2026-08-12 als Meldung 4
        # ("Das Verb steht im Relativsatz immer am Ende.") und als Meldung 6. Geprüft
        # wird der inhaltstragende Satz und nicht ``front``: bei Richtig/Falsch steckt
        # die Aussage dort, beim Umformen die Lösung.
        if names_the_form(claim, target_form):
            logger.debug("KI Tutor: Grammatik-Aufgabe nennt die Zielform: {!r}", claim)
            continue
        # Die Anweisung steht an JEDER Aufgabe. Ohne sie sieht der Lernende einen
        # nackten Satz und weiss nicht, was zu tun ist. Leerzeile dazwischen, sonst
        # ist nicht klar, worauf sich die Anweisung bezieht.
        anweisung = task_line(kind, locale, target_form, eigene_zeilen)
        item["front"] = (f"**{anweisung}**\n\n{item['front']}" if item["front"]
                         else f"**{anweisung}**")
        item["explanation"] = (ex.get("explanation") or "").strip() or None
        # Welchen nummerierten Abschnitt das Modell benutzt haben will. Wird nicht
        # gespeichert, der Aufrufer prüft damit die Abdeckung.
        item["_section"] = ex.get("section")
        # Die Seite, aus der das Modell den Stoff genommen haben will. Liest und
        # entfernt attach_chips_cited, nachdem es sie gegen die gesehenen Seiten prüft.
        item["_page"] = ex.get("page")
        # Welche Art die Aufgabe geworden ist. Nur fuer die Zaehlung des Nachschlags,
        # vor dem Speichern wieder entfernt.
        item["_kind"] = kind
        items.append(item)
        claims.append(claim)
    return items, claims


def _repeats_example(front: str, banned: set) -> bool:
    """Ob der Aufgabentext den Musterssatz wiederholt.

    Auch als Lueckensatz: dort ist ein Wort durch die Luecke ersetzt, der Rest steht
    aber wortgleich da. Deshalb wird die Luecke vorher entfernt und der Rest verglichen.
    """
    plain = normalize(front.replace(GAP, " "))
    for text in banned:
        if not text:
            continue
        if plain == text:
            return True
        # Luecken-Fassung: der Musterssatz ohne genau ein Wort.
        words, ref = plain.split(), text.split()
        if len(words) == len(ref) - 1 and all(w in ref for w in words):
            return True
    return False


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
        extras = {"pattern_front": example["before"],
                  "pattern_back": example["after"]}
        # Weitere gueltige Fassungen. Sie tragen die Pruefung: die laeuft ohne Modell
        # und kennt nur, was hier steht. Durchgelassen wird nur, was auch als Loesung
        # taugt, also eine echte Umformung und nicht schon die Musterloesung.
        accepts, seen = [], {normalize(after)}
        for alt in (ex.get("also_ok") or [])[:3]:
            alt = str(alt).strip()
            if not is_usable_pair(before, alt) or normalize(alt) in seen:
                continue
            seen.add(normalize(alt))
            accepts.append(alt)
        if accepts:
            extras["accepts"] = accepts
        return {"front": before, "back": after, "extras": extras}, after

    if kind == "cloze":
        sentence = (ex.get("sentence") or "").strip()
        span = (ex.get("form_span") or "").strip()
        options = [str(o).strip() for o in (ex.get("options") or [])]
        idx = ex.get("correct_idx")
        if not is_usable_cloze(sentence, span, options, idx):
            return None
        # Der Satz, an dem die Quelle hängt, ist jetzt der Ausgangssatz selbst. Er ist
        # vollständig und richtig, die Lücke kommt erst danach hinein, und damit ist er
        # auch der beste Text für die Suche.
        return ({"front": cut_gap(sentence, span), "back": options[idx],
                 "options": options, "correct_idx": idx},
                sentence)

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
        # Ist der Satz selbst die richtige Option, lautet die Aufgabe "welcher Satz
        # ist korrekt?". Dann traegt die Anweisung alles Noetige und der Satz stuende
        # zweimal da, oben und als erste Option. Bei der anderen Bauart ("hier ein
        # Aktivsatz, waehle das Passiv") ist er die Vorlage und bleibt.
        asks_which = normalize(sentence) == normalize(options[idx])
        return {"front": "" if asks_which else sentence, "back": options[idx],
                "options": options, "correct_idx": idx}, options[idx]

    # Eine Art, die es nicht gibt. Zu raten wäre schlimmer als wegzulassen.
    return None
