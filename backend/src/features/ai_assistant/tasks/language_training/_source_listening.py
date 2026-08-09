"""Hör- und Leseverstehen aus Quelltext (mode='source').

Läuft mechanisch wie das Quiz: EIN wanderndes Fenster über alle gewählten Quellen,
eine Aufgabe je Stelle, verteilt über die nummerierten Abschnitte des Kontexts. Fünfzehn
Aufgaben kommen damit aus fünfzehn verschiedenen Stellen und nicht aus einem Absatz.

Der Unterschied zum Quiz liegt in der Form, und deshalb ist es nur eine Form: eine
Aussage über das Material, zwei Optionen, Richtig oder Falsch. Das Quiz prüft Fachwissen
an vier Optionen, hier wird geprüft, ob jemand verstanden hat, was die Quelle sagt. Wäre
auch hier eine Aufgabe mit vier Optionen dabei, wäre der Unterschied nicht mehr zu sehen,
und genau darum geht es.

Es gab bis zum 2026-08-09 drei weitere Arten mit vier Optionen (umformulierter Satz,
Bezugswort, Schlussfolgerung). Sie sind ersatzlos weg, und mit ihnen alles, was nur
ihretwegen da war: der Aufgabenplan mit Anteilen je Art, die Sperre gegen abgedruckten
Ton aus einer Aufnahme (nur zitierende Arten konnten das) und der Wortabgleich gegen
Weltwissen (er galt den Optionen und lief für Aussagen ohnehin nie).

Das Sprachniveau steuert eine einzige Zeile: bis B1 sagt die Aussage etwas, das im
Material steht, ab B2 darf sie auch etwas sagen, das daraus folgt. Ohne diese Zeile wäre
jede Aufgabe Wiedererkennen, und für C1 ist das keine Übung mehr.

Die Beispielaufgaben stehen hinter dem Quellmaterial und nicht im System-Prompt.
Erfahrung aus dem Grammatik-Quiz: davor werden sie als Aufgabe 1 abgeschrieben, dahinter
wirken sie als Form.
"""

import json

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.services.aia_grammar_check import normalize

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips_cited
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._title import title_from_items


# Feste Beschriftung statt einer vom Modell erfundenen: es schrieb sonst mal "Wahr",
# mal "richtig", und die Ansicht zeigt die Optionen unverändert an.
_VERDICT_LABELS = {"de": ("Richtig", "Falsch"), "en": ("True", "False")}

_LEVELS_ADVANCED = {"B2", "C1", "C2"}

# Regeln aus der Testkonstruktion. Ohne sie ist die Aufgabe ohne die Quelle lösbar:
# Absolutwörter wie "immer" sind fast immer falsch, Weichmacher wie "in der Regel" fast
# immer richtig, wörtlich übernommene Sätze prüfen Wiedererkennung statt Verstehen, und
# ein Modell ohne Vorgabe schreibt fast nur wahre Sätze.
_TRUE_FALSE_RULES = (
    "\nRULES FOR THE STATEMENTS (a statement that breaks one of these can be marked "
    "right without having read or heard the source):\n"
    "- About half of the statements must be false. Do not follow a pattern.\n"
    "- One statement, one idea. Short and unambiguous.\n"
    "- Never use absolute words (always, never, all, none, nobody) and never use hedges "
    "(usually, mostly, as a rule). Both give the answer away.\n"
    "- No negation inside the statement.\n"
    "- Never copy the source verbatim, always say it in your own words.\n"
    "- Make a statement false by changing exactly one detail: a number, a person, a role, "
    "a time, a direction, or a cause. Never invent something the source does not mention "
    "at all, that is too easy to spot.\n"
    "- True and false statements must be about the same length.\n"
)

# Warum das kein zweites Quiz ist. Steht als eigener Block da, weil das Modell sonst in
# die Wissensfrage zurückfällt, die es aus jedem Fachtext am leichtesten baut.
_COMPREHENSION_RULE = (
    "\nTHIS IS NOT A KNOWLEDGE QUIZ. Never write a statement about a definition, a number "
    "or a technical fact for its own sake. Every statement is about a place in the "
    "material and asks whether the learner UNDERSTOOD what is said there. A statement of "
    'the form "X ist als Y definiert" is wrong here.\n'
)

# Bis B1 steht die Aussage im Material, ab B2 darf sie daraus folgen. Eine Zeile statt
# einer eigenen Aufgabenart: die Form bleibt in beiden Fällen Richtig/Falsch.
_REACH_BASIC = (
    "- Every statement is about something the material says directly. Never about "
    "something that merely follows from it.\n"
)
_REACH_ADVANCED = (
    "- Some of the statements say something that FOLLOWS from the material without being "
    "written in it, and the learner has to draw that conclusion. The others stay close to "
    "the material.\n"
)

_PERSONAL_RULE = (
    "- Do NOT use personal names in statements. Instead of 'laut Prof. X', write "
    "'laut Quelle' (German) or 'according to the source' (English), matching the output "
    "language.\n"
)
_VOCABULARY_RULE = (
    "- Never write a statement about what a single word means. That tests vocabulary, "
    "not comprehension.\n"
)
_SOURCE_RULE = (
    "- For every item, include source_label and page_number, the source/page it came from.\n"
)
_TITLE_RULE = (
    "- title: a short, concrete topic title in {language} (max 6 words), no quotation "
    "marks, never a filename.\n"
)

# Zwei Beispiele HINTER dem Quellmaterial, eine wahre und eine falsche Aussage. Beim
# Grammatik-Quiz war das der Unterschied zwischen 0 und 8 brauchbaren Aufgaben: das
# Modell ahmt die Formen nach, die es zuletzt gesehen hat. Sie werden in _build_items
# gesperrt, damit sie nicht als Aufgabe 1 abgeschrieben werden.
_EXAMPLE_ITEMS = (
    ("Bei sinkender Temperatur arbeitet die Anlage weniger wirtschaftlich.", True),
    ("Die Leistungszahl steigt, wenn es draußen kälter wird.", False),
)

_EXAMPLE_BLOCK = (
    "\nTwo examples of the SHAPE to copy. They are about different material, never reuse\n"
    "their wording or their content:\n\n"
    + "\n".join(json.dumps({"statement": satz, "answer": urteil}, ensure_ascii=False)
                for satz, urteil in _EXAMPLE_ITEMS)
    + "\n"
)

# Aus denselben Sätzen abgeleitet, damit Beispiel und Sperre nicht auseinanderlaufen
# können. Sie standen früher als zweite Liste daneben und mussten von Hand mitgepflegt
# werden.
_EXAMPLE_MARKERS = frozenset(normalize(satz) for satz, _ in _EXAMPLE_ITEMS)

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
_AGAIN_RULE = (
    "\nTOP-UP ROUND. The statements you write now come ON TOP of statements that already "
    "exist, and they must all be new.\n"
    "- You may go back to a passage an earlier statement already used, as long as this "
    "statement is about a DIFFERENT aspect of it or words the same point differently.\n"
    "- Never write the same statement twice.\n"
)

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
    Jeder Wurf bestellt nur noch den Fehlbetrag.
    """
    advanced = (level or "").upper() in _LEVELS_ADVANCED
    user = _build_user(ctx, language)

    items: list[dict] = []
    seen: set[str] = set()
    title = ""
    for attempt in range(_MAX_ATTEMPTS):
        wanted = count - len(items)
        if wanted <= 0:
            break
        system = (_build_prompt(wanted, language, advanced)
                  + adaptive_suffix + title_avoidance + coverage
                  + (_AGAIN_RULE if attempt else ""))
        fresh, fresh_title = _one_call(client, model, system, user, ctx, locale, wanted)
        title = title or fresh_title
        keep = _pick(fresh, seen)
        if keep:
            # Gestaffelt wie in der Grammatik-Übung: Datei und Seite, die das Modell selbst
            # nennt, sonst die pgvector-Suche, sonst wenigstens die Datei. Die Angabe des
            # Modells wurde hier lange erfragt und dann weggeworfen, weil eine reine Suche
            # zuverlässiger schien. Sie ist es nicht: eine umformulierte Aussage findet
            # sich oft nicht wieder, und dann stand die Aufgabe ganz ohne Quelle da.
            attach_chips_cited(keep, [i.pop("_claim", "") for i in keep], ctx)
            items += keep
        if len(items) >= count:
            break
        logger.info("Hör- und Leseverstehen: Wurf {} ergab {}/{} Aufgaben",
                    attempt + 1, len(items), count)
    items = items[:count]

    if not items:
        return [], ""

    return items, title or title_from_items(client, model, items, ctx.multi_label)


def _pick(fresh: list[dict], seen: set) -> list[dict]:
    """Welche Aufgaben eines Wurfs ins Set dürfen. Merkt sich das Genommene in ``seen``.

    Was genommen wurde, ist gemerkt, auch wenn die Zuordnung es danach wieder
    aussortiert. Ein zweites Mal fiele es aus demselben Grund wieder heraus.
    """
    keep = []
    for item in fresh:
        key = normalize(item["front"])
        if key in seen or _too_close(key, seen):
            continue
        seen.add(key)
        keep.append(item)
    return keep


def _too_close(key: str, seen: set) -> bool:
    """Ob dieselbe Aufgabe schon dasteht, nur anders formuliert.

    Der Nachschlag darf ausdrücklich zu einer Stelle zurückkehren (siehe
    :data:`_AGAIN_RULE`), und genau das hat das Modell benutzt, um dieselbe Aussage ein
    zweites Mal zu behaupten. Ein Vergleich auf Gleichheit greift dann nicht mehr.
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


def _build_prompt(count: int, language: str, advanced: bool) -> str:
    return (
        f"You write reading- and listening-comprehension items about the given source "
        f"material. Everything you write must be decidable from that material alone, never "
        f"from general knowledge. Write ALL statements in {language}, regardless of the "
        f"source language. Translate if needed.\n\n"
        f"Write exactly {count} statements about the material. The learner reads or "
        f"listens to the material and then marks every statement as true or false. Take "
        f"each statement from a DIFFERENT place in the material, never several statements "
        f"about the same sentence.\n\n"
        "Respond ONLY with a JSON object. Every item is one statement plus your verdict "
        "on it, which is JSON true or false and nothing else:\n"
        '{"title": "Short topic title", "exercises": ['
        '{"statement": "...", "answer": false, "source_label": "Filename.pdf", '
        '"page_number": 7}]}\n'
        + _TRUE_FALSE_RULES
        + _COMPREHENSION_RULE
        + "\nGENERAL:\n"
        + (_REACH_ADVANCED if advanced else _REACH_BASIC)
        + _PERSONAL_RULE
        + _VOCABULARY_RULE
        + _SOURCE_RULE
        + _TITLE_RULE.replace("{language}", language)
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
    return _build_items(list(exercises)[:count], locale), title


def _build_items(exercises: list[dict], locale: str) -> list[dict]:
    """Item-Zeilen. Was durchfällt, kommt nicht ins Set.

    Der Aufgabentext steht in ``front``, die richtige Beschriftung in ``back``, dazu die
    zwei Optionen. Die Ansicht unterscheidet die Werkzeuge an der Anzahl der Optionen,
    nicht an einem eigenen Feld, und zwei Optionen heisst Richtig/Falsch.

    Eine Aufgabe mit vier Optionen fällt hier durch, auch wenn der Prompt sie nie
    bestellt hat. Das Modell liefert sie trotzdem gelegentlich, und dann sähe das
    Werkzeug aus wie das Quiz.
    """
    yes, no = _verdict_labels(locale)
    items: list[dict] = []
    for exercise in exercises:
        statement = (exercise.get("statement") or "").strip()
        verdict = exercise.get("answer")
        if not statement or not isinstance(verdict, bool):
            continue
        if normalize(statement) in _EXAMPLE_MARKERS:
            continue

        items.append({
            "front": statement,
            "back": yes if verdict else no,
            "options": [yes, no],
            "correct_idx": 0 if verdict else 1,
            # Welchen nummerierten Abschnitt das Modell benutzt haben will. Wird nicht
            # gespeichert, der Aufrufer prüft damit, ob jeder Abschnitt drankam.
            "_section": exercise.get("section"),
            # Text für die Attribution. Wird vor dem Speichern wieder entfernt. Gesucht
            # wird über die Aussage und nicht über "Richtig"/"Falsch": die feste
            # Beschriftung steht in keiner Quelle und würde die Suche verwässern.
            "_claim": statement,
            # Woher das Modell die Aufgabe genommen haben will. Beides wird gegen den
            # Kontext geprüft und danach entfernt.
            "_source_label": (exercise.get("source_label") or "").strip(),
            "_page": exercise.get("page_number"),
        })
    return items
