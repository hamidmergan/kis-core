"""Hör- und Leseverstehen aus Quelltext (mode='source').

Läuft mechanisch wie das Quiz: EIN wanderndes Fenster über alle gewählten Quellen,
eine Frage je Stelle, verteilt über die nummerierten Abschnitte des Kontexts. Fünfzehn
Aufgaben kommen damit aus fünfzehn verschiedenen Stellen und nicht aus einem Absatz.

Der Unterschied zum Quiz liegt allein in der Frageart. Das Quiz prüft Fachwissen
("Was ist X?"), hier wird geprüft, ob jemand verstanden hat, was die Quelle sagt:

* Richtig/Falsch zu einer umformulierten Aussage
* sinngemäße Wiedergabe eines zitierten Satzes
* Bezugswort: worauf verweist "sie" in diesem Satz
* Schlussfolgerung: was folgt daraus, ohne dort zu stehen

Aufnahmen bekommen nur Richtig/Falsch und Schlussfolgerung. Die beiden anderen Arten
zitieren Wortlaut, und geschriebener Wortlaut aus einer Aufnahme macht aus der Hörübung
wieder eine Leseübung.

Die Mischung steht als ZAHL im Prompt, nicht als Absicht. Erfahrung aus dem
Grammatik-Quiz: "stelle abwechslungsreiche Fragen" wirkt nicht, "genau 4 Aufgaben der
Art X" wirkt. Die Beispielaufgaben stehen hinter dem Quellmaterial und nicht im
System-Prompt, auch das hat dort erst den Ausschlag gegeben.
"""

import json

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.services.aia_chunker import is_media_file
from src.services.aia_grammar_check import normalize

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips_cited
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._plan import (
    plan_sentence,
    room_left,
    still_missing,
)
from src.features.ai_assistant.tasks.language_training._title import title_from_items


# Feste Beschriftung statt einer vom Modell erfundenen: es schrieb sonst mal "Wahr",
# mal "richtig", und die Ansicht zeigt die Optionen unverändert an.
_VERDICT_LABELS = {"de": ("Richtig", "Falsch"), "en": ("True", "False")}

# Ab hier gilt eine Antwort als im Quellmaterial vorhanden. Kein wörtlicher Vergleich:
# das Modell formuliert um, und genau das soll es auch.
_MIN_ANSWER_COVERAGE = 0.6

# Diese Arten dürfen nicht wörtlich im Material stehen, für sie greift der Wortabgleich
# also nicht. Eine Schlussfolgerung folgt aus dem Text, ohne dort zu stehen, und eine
# falsche Aussage steht dort nie.
_UNGROUNDED_KINDS = {"statement", "inference"}

# Diese Arten zitieren Wortlaut. Aus einer Aufnahme darf keine davon kommen, sonst liest
# der Lernende den gesprochenen Satz, statt ihn zu hören.
_QUOTING_KINDS = {"paraphrase", "reference"}

_LEVELS_ADVANCED = {"B2", "C1", "C2"}

_KIND_RULES = {
    "statement": "statement: a claim about the material that the learner marks as true "
                 "or false.",
    "paraphrase": "paraphrase: quote ONE sentence from the material inside the question "
                  "and ask which option says the same thing in other words. The three "
                  "wrong options must be about the same sentence, changed in one point.",
    "reference": "reference: quote ONE sentence from the material that contains a "
                 "pronoun or a reference word (it, this, they, there) and ask what that "
                 "word refers back to. Every option must be a noun phrase that actually "
                 "appears in the material.",
    "inference": "inference: one question whose answer follows from the material without "
                 "being written in it. Never a question that can be answered by copying "
                 "a sentence.",
}

# Regeln aus der Testkonstruktion. Ohne sie ist der Aufgabentyp ohne die Quelle lösbar:
# Absolutwörter wie "immer" sind fast immer falsch, Weichmacher wie "in der Regel" fast
# immer richtig, wörtlich übernommene Sätze prüfen Wiedererkennung statt Verstehen, und
# ein Modell ohne Vorgabe schreibt fast nur wahre Sätze.
_TRUE_FALSE_RULES = (
    "\nRULES FOR THE statement ITEMS (an item that breaks one of these can be solved "
    "without having read or heard the source):\n"
    "- About half of the statements must be false. Do not follow a pattern.\n"
    "- One statement, one idea. Short and unambiguous.\n"
    "- Never use absolute words (always, never, all, none, nobody) and never use hedges "
    "(usually, mostly, as a rule). Both give the answer away.\n"
    "- No negation inside the statement.\n"
    "- Never copy the source verbatim, always paraphrase it.\n"
    "- Make a statement false by changing exactly one detail: a number, a person, a role, "
    "a time, a direction, or a cause. Never invent something the source does not mention "
    "at all, that is too easy to spot.\n"
    "- True and false statements must be about the same length.\n"
)

# Warum das kein zweites Quiz ist. Steht als eigener Block da, weil das Modell sonst in
# die Wissensfrage zurückfällt, die es aus jedem Fachtext am leichtesten baut.
_COMPREHENSION_RULE = (
    "\nTHIS IS NOT A KNOWLEDGE QUIZ. Never ask for a definition, a number or a technical "
    "fact for its own sake. Every item asks whether the learner UNDERSTOOD a place in the "
    "material: what it says, what a word in it refers to, or what follows from it. "
    'A question of the form "Was bedeutet X?" or "Wie viele Y gibt es?" is wrong here.\n'
)

_PERSONAL_RULE = (
    "- Do NOT use personal names in questions. Instead of 'laut Prof. X', write "
    "'laut Quelle' (German) or 'according to the source' (English), matching the output "
    "language.\n"
)
_SOURCE_RULE = (
    "- For every item, include source_label and page_number, the source/page it came from.\n"
)
_TITLE_RULE = (
    "- title: a short, concrete topic title in {language} (max 6 words), no quotation "
    "marks, never a filename.\n"
)

# Drei Beispiele HINTER dem Quellmaterial. Beim Grammatik-Quiz war das der Unterschied
# zwischen 0 und 8 brauchbaren Aufgaben: das Modell ahmt die Formen nach, die es zuletzt
# gesehen hat. Die Beispiele werden in _build_items gesperrt, damit sie nicht als
# Aufgabe 1 abgeschrieben werden.
_EXAMPLE_BLOCK = """
Three examples of the SHAPE to copy. They are about different material, never reuse
their wording or their content:

{"kind": "paraphrase", "question": "Die Quelle sagt: \\"Sinkt die Außentemperatur, fällt die Leistungszahl.\\" Was heißt das?",
 "options": ["Bei Kälte arbeitet die Anlage weniger wirtschaftlich", "Bei Kälte schaltet die Anlage ab",
             "Die Leistungszahl steigt mit der Kälte", "Die Außentemperatur hängt von der Anlage ab"],
 "correct_idx": 0}
{"kind": "reference", "question": "Worauf bezieht sich \\"sie\\" in \\"Sinkt die Temperatur, fällt sie\\"?",
 "options": ["auf die Wärme", "auf die Leistungszahl", "auf die Temperatur", "auf die Luft"],
 "correct_idx": 1}
{"kind": "statement", "statement": "Bei sinkender Temperatur arbeitet der Verdichter weniger."
 , "answer": false}
"""

_EXAMPLE_MARKERS = (
    "worauf bezieht sich sie in sinkt die temperatur fallt sie",
    "bei sinkender temperatur arbeitet der verdichter weniger",
)

# Bis zu drei Würfe, damit die bestellte Anzahl zusammenkommt. Die Filter werfen weg,
# und wer fünfzehn Aufgaben bestellt, will fünfzehn. Mehr als drei bringt nichts: das
# Anfragen-Kontingent ist hochschulweit geteilt, und wer dreimal nichts Brauchbares
# liefert, liefert es beim vierten Mal auch nicht.
_MAX_ATTEMPTS = 3

# Der Nachschlag hebt eine Regel des ersten Wurfs auf. Sie lautet dort, jede Aufgabe
# müsse von einer ANDEREN Stelle kommen, und das ist richtig, solange genug Stellen da
# sind. Steht die Anzahl danach nicht, ist genau diese Regel die Bremse: eine kurze
# Quelle hat irgendwann keine unberührte Stelle mehr. Dann zählt die Anzahl mehr, und
# dieselbe Stelle darf ein zweites Mal drankommen, sofern anders gefragt wird.
#
# Die schon geschriebenen Aufgaben werden dem Modell dabei NICHT vorgelegt. Das wurde
# an anderer Stelle versucht und verworfen (siehe _variation): im Prompt wirken sie als
# Muster und werden wörtlich abgeschrieben. Doppler fängt der Code ab.
# Steckt so viel vom kürzeren Aufgabentext im längeren, gilt die Aufgabe als dieselbe,
# nur anders formuliert. Sprach-unabhängig, keine Wortlisten.
#
# Gemessen und nicht geraten (2026-08-06, Sets 1780 und 1783). Dort standen je zwei
# Aufgaben doppelt im Set, einmal dieselbe Frage ausführlicher gestellt (1,00) und
# einmal derselbe Satz mit anderem Monat und einem Nebensatz dahinter (0,89). Zwei
# Aufgaben, die wirklich nach Verschiedenem fragen, lagen bei 0,63 und darunter, auch
# wenn sie dieselbe Sache betrafen. Die Grenze liegt dazwischen.
#
# Warum nicht overlap_ratio wie beim Ankreuzen: das teilt durch den LÄNGEREN Text, und
# ein angehängter Nebensatz drückt den Wert damit unter jede brauchbare Schwelle. Der
# zweite Fall oben käme so auf 0,53 und stünde heute noch doppelt im Set.
_MAX_CONTAINED = 0.75

# Darunter ist ein Aufgabentext zu kurz, um ihn über seine Wörter zu vergleichen: drei
# Wörter stecken schnell in irgendeinem längeren Satz, ohne dasselbe zu meinen.
_MIN_WORDS_TO_COMPARE = 4

_AGAIN_RULE = (
    "\nTOP-UP ROUND. The items you write now come ON TOP of items that already exist, "
    "and they must all be new.\n"
    "- You may go back to a passage an earlier item already used, as long as this item "
    "asks about a DIFFERENT aspect of it or words the same point differently.\n"
    "- Never write the same question or the same statement twice.\n"
)


def generate_listening_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    locale: str = "de",
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
    level: str | None = None,
) -> tuple[list[dict], str]:
    """Bis zu drei Würfe über den ganzen Kontext. Liefert (items, title).

    Geworfen wird so lange, bis die bestellte Anzahl steht, höchstens aber dreimal.
    Der Nachschlag fragt gezielt nach den Arten, die noch fehlen, sonst kippt die
    Mischung: das Modell liefert am liebsten Richtig/Falsch-Aussagen.

    Jeder Wurf wird sofort zugeordnet und gefiltert, nicht erst am Ende. Nur so weiss
    der nächste Wurf, wie viele Aufgaben wirklich überlebt haben: die Sperre gegen
    abgedruckten Ton (:func:`drop_quotes_on_recordings`) greift erst NACH der
    Zuordnung, und sie hat Sets bisher stillschweigend verkürzt.
    """
    recordings = _recording_labels(ctx)
    sections = _recording_sections(ctx, recordings)
    advanced = (level or "").upper() in _LEVELS_ADVANCED
    plan = item_plan(count, advanced=advanced,
                     text_ok=len(recordings) < len(ctx.source_by_name))
    user = _build_user(ctx, language)

    items: list[dict] = []
    seen: set[str] = set()
    title = ""
    lost_to_recordings = 0
    for attempt in range(_MAX_ATTEMPTS):
        wanted = still_missing(plan, items)
        if not wanted:
            break
        # Hat die Aufnahme-Sperre schon zugeschlagen, wird nur noch bestellt, was sie
        # nicht wegwerfen kann. Sonst wiederholt sich der Verlust in jedem Wurf: das
        # Modell legt die zitierenden Arten wieder auf die Aufnahme, die Sperre wirft
        # sie wieder weg, und das Set bleibt kurz. Gemessen am 2026-08-06: 9 von 10.
        if lost_to_recordings:
            wanted = item_plan(len(wanted), advanced=advanced, text_ok=False)
        system = (_build_prompt(wanted, language, sections)
                  + adaptive_suffix + title_avoidance + coverage
                  + (_AGAIN_RULE if attempt else ""))
        fresh, fresh_title = _one_call(client, model, system, user, ctx, locale, count)
        title = title or fresh_title
        # Bis zum letzten Wurf gilt der Deckel je Art. Im LETZTEN zählt die Anzahl mehr
        # als die Mischung, denn wer fünfzehn bestellt hat, will fünfzehn. Nach einem
        # Verlust an die Aufnahme-Sperre fällt er auch: die bestellten Arten stehen
        # dann nicht mehr im Plan und würden am eigenen Deckel scheitern.
        last_try = attempt == _MAX_ATTEMPTS - 1
        open_run = last_try or lost_to_recordings
        keep = _pick(fresh, seen, {} if open_run else room_left(plan, items))
        if keep:
            # Gestaffelt wie in der Grammatik-Übung: Datei und Seite, die das Modell selbst
            # nennt, sonst die pgvector-Suche, sonst wenigstens die Datei. Die Angabe des
            # Modells wurde hier lange erfragt und dann weggeworfen, weil eine reine Suche
            # zuverlässiger schien. Sie ist es nicht: eine umformulierte Aussage findet
            # sich oft nicht wieder, und dann stand die Aufgabe ganz ohne Quelle da. Für
            # Aufnahmen zählt die Angabe weiterhin nicht, siehe attach_chips_cited.
            attach_chips_cited(keep, [i.pop("_claim", "") for i in keep], ctx)
            survived = drop_quotes_on_recordings(keep, recordings)
            lost_to_recordings += len(keep) - len(survived)
            items += survived
        if len(items) >= count:
            break
        logger.info("Hör- und Leseverstehen: Wurf {} ergab {}/{} Aufgaben",
                    attempt + 1, len(items), count)
    items = items[:count]

    if not items:
        return [], ""

    for item in items:
        item.pop("_kind", None)

    return items, title or title_from_items(client, model, items, ctx.multi_label)


def _pick(fresh: list[dict], seen: set, room: dict) -> list[dict]:
    """Welche Aufgaben eines Wurfs ins Set dürfen. Merkt sich das Genommene in ``seen``.

    Was am Deckel scheitert, wird NICHT gemerkt: im letzten Wurf gibt es keinen Deckel
    mehr, und dann darf dieselbe Aufgabe doch noch hinein. Was genommen wurde, ist
    gemerkt, auch wenn die Zuordnung es danach wieder aussortiert. Ein zweites Mal
    fiele es aus demselben Grund wieder heraus.
    """
    keep = []
    for item in fresh:
        key = normalize(item["front"])
        if key in seen or _too_close(key, seen):
            continue
        # Eine Art, die im Plan nicht vorkommt, hat keinen Deckel. Das Modell lässt das
        # Feld manchmal weg, und eine Aufgabe wegen einer fehlenden Beschriftung
        # wegzuwerfen wäre der falsche Preis.
        kind = item.get("_kind") or ""
        if kind in room:
            if room[kind] <= 0:
                continue
            room[kind] -= 1
        seen.add(key)
        keep.append(item)
    return keep


def _too_close(key: str, seen: set) -> bool:
    """Ob dieselbe Aufgabe schon dasteht, nur anders formuliert.

    Der Nachschlag darf ausdrücklich zu einer Stelle zurückkehren (siehe
    :data:`_AGAIN_RULE`), und genau das hat das Modell benutzt, um dieselbe Frage ein
    zweites Mal zu stellen. Ein Vergleich auf Gleichheit greift dann nicht mehr.
    """
    return any(_contained(key, other) >= _MAX_CONTAINED for other in seen)


def _contained(one: str, other: str) -> float:
    """Anteil des KÜRZEREN Textes, der im längeren steckt. 0.0 bis 1.0.

    Vielfachheit zählt mit: ein Wort, das einmal dasteht, deckt kein Wort ab, das
    zweimal gebraucht wird.
    """
    short, long = sorted((one.split(), other.split()), key=len)
    if len(short) < _MIN_WORDS_TO_COMPARE:
        return 0.0
    pool = list(long)
    hits = 0
    for word in short:
        if word in pool:
            pool.remove(word)
            hits += 1
    return hits / len(short)


def drop_quotes_on_recordings(items: list[dict], recordings: list[str]) -> list[dict]:
    """Wirft zitierende Aufgaben weg, deren Fundstelle eine Aufnahme ist.

    Der Prompt verbietet das schon, am echten Lauf hat sich das Modell aber nicht daran
    gehalten: von 15 Aufgaben lagen 4 als "Die Quelle sagt: ..." auf einem Video. Die
    Regel muss deshalb im Code stehen und nicht nur im Prompt.

    Erst NACH der Attribution möglich: vorher steht die Quelle einer Aufgabe nicht fest.
    Das Set wird dadurch kürzer, das ist der Preis. Ein kurzes Set ist kurz, ein Set mit
    abgedrucktem Ton ist falsch.
    """
    heard = set(recordings)
    keep = []
    for item in items:
        # ``_kind`` bleibt an der Aufgabe: der Aufgabenplan zählt danach, wie viel von
        # welcher Art schon steht. Entfernt wird es erst vor dem Speichern.
        kind = item.get("_kind") or ""
        labels = {s.get("source_label") for s in item.get("sources") or []}
        labels.add(item.get("source_label"))
        if heard and kind in _QUOTING_KINDS and labels & heard:
            continue
        keep.append(item)
    dropped = len(items) - len(keep)
    if dropped:
        logger.info("Hör- und Leseverstehen: {} zitierende Aufgaben lagen auf einer "
                    "Aufnahme und sind raus", dropped)
    return keep


def _recording_labels(ctx: QuelleContext) -> list[str]:
    """Dateinamen der Aufnahmen in diesem Kontext."""
    return [label for label, source in ctx.source_by_name.items()
            if is_media_file(source.get("file_type") or "")]


def _recording_sections(ctx: QuelleContext, recordings: list[str]) -> list[str]:
    """Die Aufnahmen so benannt, wie sie im Material stehen.

    Mit Abschnittsnummer, wo es eine gibt. Der Dateiname allein hat nicht gereicht: das
    Material trägt die Nummer im Kopf jedes Abschnitts, und das Modell greift danach.
    """
    by_label = {label: num for num, label in (ctx.sections or {}).items()}
    return [f"SECTION {by_label[label]} ({label})" if label in by_label else label
            for label in recordings]


def item_plan(count: int, *, advanced: bool, text_ok: bool) -> list[str]:
    """Welche Frageart wie oft. Zählbar, weil eine Absichtserklärung nicht wirkt.

    Ohne geschriebene Quelle fallen die zitierenden Arten weg: ein zitierter Satz aus
    einer Aufnahme ist der Wortlaut, und dann liest der Lernende wieder, statt zu hören.
    Die Schlussfolgerung kommt erst ab B2 dazu, darunter überfordert sie.
    """
    if not text_ok:
        cycle = ["statement", "inference"] if advanced else ["statement"]
    elif advanced:
        cycle = ["statement", "paraphrase", "inference", "reference"]
    else:
        cycle = ["statement", "paraphrase", "reference", "statement"]
    return [cycle[i % len(cycle)] for i in range(max(0, count))]


def _build_prompt(plan: list[str], language: str, recordings: list[str]) -> str:
    kinds = list(dict.fromkeys(plan))
    rules = "".join(f"- {_KIND_RULES[k]}\n" for k in kinds if k in _KIND_RULES)
    title_rule = _TITLE_RULE.replace("{language}", language)
    shape_kind = next((k for k in kinds if k != "statement"), "inference")
    # Der Wortlaut einer Aufnahme darf nicht in der Frage stehen. Die Regel wird nur
    # gesetzt, wenn überhaupt eine Aufnahme dabei ist, sonst ist sie Rauschen.
    media_rule = ""
    if recordings:
        listing = ", ".join(recordings)
        media_rule = (
            f"\nRECORDINGS. This material is spoken, the learner LISTENS to it: {listing}.\n"
            "- NEVER put a sentence from a recording in quotation marks in your question. "
            'An item taken from a recording must be of kind "statement" or "inference", '
            'never "paraphrase" and never "reference".\n'
            "- The learner sees no transcript. An item from a recording must be answerable "
            "after listening, without any written text to read.\n"
            "- Take the quoting kinds from the written sections instead.\n"
        )
    return (
        f"You write reading- and listening-comprehension items about the given source "
        f"material. Everything you ask must be decidable from that material alone, never "
        f"from general knowledge. Write ALL questions, statements, options and answers in "
        f"{language}, regardless of the source language. Translate if needed.\n\n"
        f"Write exactly {len(plan)} items: {plan_sentence(plan)}. Take each item from a "
        f"DIFFERENT place in the material, never several items about the same sentence.\n\n"
        f"The kinds:\n{rules}\n"
        "Respond ONLY with a JSON object. Every item carries its \"kind\". A statement "
        "item uses \"statement\" plus \"answer\" (JSON true or false) and brings no "
        "options. Every other kind uses \"question\", \"options\" (exactly 4) and "
        "\"correct_idx\":\n"
        '{"title": "Short topic title", "exercises": ['
        f'{{"kind": "{shape_kind}", "question": "...", "options": ["A", "B", "C", "D"], '
        '"correct_idx": 0, "source_label": "Filename.pdf", "page_number": 5}, '
        '{"kind": "statement", "statement": "...", "answer": false, '
        '"source_label": "Filename.pdf", "page_number": 7}]}\n'
        + (_TRUE_FALSE_RULES if "statement" in kinds else "")
        + media_rule
        + _COMPREHENSION_RULE
        + "\nGENERAL:\n"
        + _PERSONAL_RULE
        + "- Never ask what a single word means. That tests vocabulary, not comprehension.\n"
        + "- The four options of an item must differ from each other and none of them may "
          "repeat the question.\n"
        + _SOURCE_RULE
        + title_rule
    )


def _build_user(ctx: QuelleContext, language: str) -> str:
    """Quellmaterial zuerst, Beispiele dahinter.

    Die Reihenfolge ist nicht Geschmack: ein Beispiel im System-Prompt wurde auf
    Fachquellen als Aufgabe 1 abgeschrieben, hinter dem Material wirkt es als Form.
    """
    return (f"Write the output in {language}.\n\nSources:\n\n{ctx.context}\n\n"
            f"{_EXAMPLE_BLOCK}")


def _verdict_labels(locale: str) -> tuple[str, str]:
    return _VERDICT_LABELS["en" if (locale or "").lower().startswith("en") else "de"]


def answer_is_grounded(answer: str, material: str) -> bool:
    """Steht die richtige Antwort im Quellmaterial?

    Der Prüfstein gegen Weltwissen. Kein wörtlicher Vergleich, sondern der Anteil der
    Antwortwörter, die im Material vorkommen: das Modell formuliert um, und das soll es
    auch. Sprach-unabhängig, keine Wortlisten.
    """
    words = normalize(answer).split()
    if not words:
        return False
    pool = set(normalize(material).split())
    hits = sum(1 for word in words if word in pool)
    return hits / len(words) >= _MIN_ANSWER_COVERAGE


def _one_call(client, model, system: str, user: str, ctx: QuelleContext, locale: str,
              count: int) -> tuple[list[dict], str]:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.6)
    try:
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
    except (json.JSONDecodeError, TypeError):
        logger.warning("Hör- und Leseverstehen: unbrauchbares JSON")
        return [], ""
    if isinstance(data, dict):
        exercises = data.get("exercises") or []
        title = (data.get("title") or "").strip()
    else:
        exercises, title = data, ""
    return _build_items(list(exercises)[:count], ctx, locale), title


def _build_items(exercises: list[dict], ctx: QuelleContext, locale: str) -> list[dict]:
    """Item-Zeilen. Was durchfällt, kommt nicht ins Set.

    Alle Arten teilen eine Form: Aufgabentext in ``front``, richtige Option in ``back``,
    dazu ``options`` und ``correct_idx``. Die Ansicht unterscheidet sie an der Anzahl der
    Optionen, nicht an einem eigenen Feld.
    """
    yes, no = _verdict_labels(locale)
    items: list[dict] = []
    for exercise in exercises:
        kind = (exercise.get("kind") or "").strip().lower()
        statement = (exercise.get("statement") or "").strip()

        if statement or kind == "statement":
            verdict = exercise.get("answer")
            if not statement or not isinstance(verdict, bool):
                continue
            # Die Fundstelle wird über die Aussage gesucht, nicht über "Richtig"/"Falsch":
            # die feste Beschriftung steht in keiner Quelle und würde die Suche verwässern.
            front, options, idx, claim = statement, [yes, no], (0 if verdict else 1), statement
            # Die Art wird festgeschrieben, auch wenn das Modell das Feld weggelassen hat.
            # Sonst zählt der Aufgabenplan sie nicht mit und der Nachschlag bestellt
            # Richtig/Falsch-Aussagen, die längst dastehen.
            kind = "statement"
        else:
            front = (exercise.get("question") or "").strip()
            options = [str(o).strip() for o in (exercise.get("options") or []) if str(o).strip()]
            idx = exercise.get("correct_idx")
            if not front or len(options) < 2 or not isinstance(idx, int):
                continue
            if not 0 <= idx < len(options):
                continue
            if len(set(normalize(o) for o in options)) != len(options):
                continue
            if normalize(options[idx]) == normalize(front):
                continue
            # Weltwissen-Sperre. Eine Schlussfolgerung steht bewusst nicht im Material,
            # für sie greift nur, dass das Modell nichts anderes gesehen hat.
            if kind not in _UNGROUNDED_KINDS and not answer_is_grounded(options[idx], ctx.context):
                continue
            claim = f"{front} {options[idx]}".strip()

        if normalize(front) in _EXAMPLE_MARKERS:
            continue

        items.append({
            "front": front,
            "back": options[idx],
            "options": options,
            "correct_idx": idx,
            # Welchen nummerierten Abschnitt das Modell benutzt haben will. Wird nicht
            # gespeichert, der Aufrufer prüft damit, ob jeder Abschnitt drankam.
            "_section": exercise.get("section"),
            # Text für die Attribution. Wird vor dem Speichern wieder entfernt.
            "_claim": claim,
            # Woher das Modell die Aufgabe genommen haben will. Der Prompt fragt beides
            # seit jeher ab (_SOURCE_RULE), jetzt wird die Antwort auch benutzt. Beides
            # wird gegen den Kontext geprüft und danach entfernt.
            "_source_label": (exercise.get("source_label") or "").strip(),
            "_page": exercise.get("page_number"),
            # Zitiert die Aufgabe Wortlaut? Entscheidet nach der Attribution, ob sie auf
            # einer Aufnahme liegen darf. Wird ebenfalls wieder entfernt.
            "_kind": kind,
        })
    return items
