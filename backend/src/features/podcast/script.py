"""The model call that turns material into a conversation, and the check of its answer."""

import json
import re

from loguru import logger

from src.features.podcast import glossary as glossar
from src.services import anweisung
from src.features.podcast.schemas import LENGTH_PLAN, Line, PodcastParams
from src.limits import PODCAST_MAX_LINES, PODCAST_MAX_LINE_CHARS

_ROLE_DE = {
    "host": "Moderation, führt durch die Folge, fragt nach und bringt eigene Beobachtungen und Beispiele ein",
    "expert": "Fachperson, erklärt die Sache und bringt Beispiele",
    "student": "Studierende Person, fragt nach, wenn etwas unklar bleibt",
    "critic": "Kritische Stimme, benennt Grenzen und Einwände",
}
_ROLE_EN = {
    "host": "host, leads through the episode, asks back and brings own observations and examples",
    "expert": "expert, explains the matter and brings examples",
    "student": "student, asks again when something stays unclear",
    "critic": "critical voice, names limits and objections",
}
_STYLE_DE = {
    "teaching": "erklärend und anschaulich, Schritt für Schritt",
    "casual": "locker und gesprächig, auch mal ein Scherz",
    "interview": "Interview, kurze Fragen und ausführliche Antworten",
}
_STYLE_EN = {
    "teaching": "explanatory and vivid, step by step",
    "casual": "casual and chatty, the odd joke is fine",
    "interview": "interview, short questions and long answers",
}


def _besetzung(params: PodcastParams) -> str:
    rollen = _ROLE_DE if params.language == "de" else _ROLE_EN
    return "\n".join(
        f"{i}: {p.name} ({rollen.get(p.role, p.role)})" for i, p in enumerate(params.persons)
    )


def teil_laengen(anzahl: int, teile: int) -> list[int]:
    """How many contributions each part of the episode gets, the first ones one more."""
    teile = max(1, min(teile, anzahl))
    grund, rest = divmod(anzahl, teile)
    return [grund + (1 if i < rest else 0) for i in range(teile)]


def _rahmen_de(teil: int, teile: int) -> str:
    if teile == 1:
        return "- Der erste Beitrag begrüßt und nennt das Thema, der letzte verabschiedet.\n"
    if teil == 1:
        return ("- Der erste Beitrag begrüßt und nennt das Thema der ganzen Folge, wie der Plan "
                "es zeigt, nicht nur das dieses Teils. Die Folge geht danach weiter, also keine "
                "Verabschiedung.\n")
    if teil == teile:
        return ("- Du setzt ein laufendes Gespräch fort, keine Begrüßung. "
                "Der letzte Beitrag verabschiedet.\n")
    return "- Du setzt ein laufendes Gespräch fort, keine Begrüßung und keine Verabschiedung.\n"


def _rahmen_en(teil: int, teile: int) -> str:
    if teile == 1:
        return "- The first contribution greets and names the topic, the last says goodbye.\n"
    if teil == 1:
        return ("- The first contribution greets and names the topic of the whole episode as the "
                "plan shows it, not only that of this part. The episode goes on afterwards, so no "
                "goodbye.\n")
    if teil == teile:
        return "- You continue a running conversation, no greeting. The last contribution says goodbye.\n"
    return "- You continue a running conversation, no greeting and no goodbye.\n"


def _bisher(bisher: list[Line], params: PodcastParams) -> str:
    if not bisher:
        return ""
    namen = [p.name for p in params.persons]
    zeilen = "\n".join(f"{namen[l.speaker] if l.speaker < len(namen) else l.speaker}: {l.text}"
                        for l in bisher)
    kopf = "Bisher zuletzt gesagt" if params.language == "de" else "Said last so far"
    return f"{kopf}:\n{zeilen}\n\n"


def _besprochen(anfaenge: list[str] | None, kopf: str) -> str:
    if not anfaenge:
        return ""
    return f"{kopf}:\n" + "\n".join(f"- {a}" for a in anfaenge) + "\n\n"


def build_messages(source: str, params: PodcastParams, *, anzahl: int | None = None,
                   teil: int = 1, teile: int = 1, plan: str = "",
                   bisher: list[Line] | None = None, opening: str = "",
                   thread: str = "", besprochen: list[str] | None = None) -> list[dict]:
    """One call, the answer is a JSON object with the list of contributions.

    A long episode is written in parts, each call writes few contributions and so stays
    inside the provider's five minutes. ``plan`` is the whole episode, ``bisher`` the last
    contributions before this part, ``opening`` the situation the first part starts with
    and ``thread`` what the last part closes on. ``besprochen`` holds the openings of all
    earlier contributions, so a later part does not explain the same thing again.
    """
    gesamt, je = LENGTH_PLAN.get(params.length, LENGTH_PLAN["medium"])
    anzahl = anzahl or gesamt
    woerter = anzahl * je
    allein = len(params.persons) == 1
    bisher = bisher or []
    if params.language == "de":
        system = (
            "Du schreibst das Skript einer Podcast-Folge für eine Hochschule. "
            "Fakten, Zahlen, Fristen und Bedingungen nimmst du ausschließlich aus dem gelieferten "
            "Material und fügst keine hinzu. Beispiele, Vergleiche und Einwände darfst du selbst "
            "bringen, damit die Sache anschaulich wird. "
            "Du antwortest mit einem JSON-Objekt der Form "
            '{"lines": [{"speaker": 0, "text": "..."}]} und mit nichts sonst.'
        )
        teilzeile = (f"Du schreibst Teil {teil} von {teile} der Folge.\n"
                     f"Plan der ganzen Folge:\n{plan}\n\n") if teile > 1 else ""
        aufgabe = (
            f"{teilzeile}Material:\n---\n{source}\n---\n\n"
            f"{_besprochen(besprochen, 'Schon besprochen, nicht wiederholen')}"
            f"{_bisher(bisher, params)}"
            f"Besetzung, die Zahl ist der Wert für speaker:\n{_besetzung(params)}\n\n"
            f"Stil: {_STYLE_DE.get(params.style, params.style)}\n"
            f"Umfang: genau {anzahl} Beiträge, zusammen rund {woerter} Wörter, im Schnitt {je} je Beitrag.\n\n"
            "Regeln:\n"
            "- Sprache des Skripts: Deutsch. Die Hörer werden durchgehend geduzt.\n"
            + ("- Es spricht nur eine Person, speaker ist immer 0.\n" if allein else
               "- Die Personen wechseln sich ab, niemand spricht zweimal hintereinander.\n"
               "- Jede Person kommt vor und behält ihre Rolle.\n"
               "- Schneller Wechsel wie in einem echten Gespräch: Etwa jeder dritte Beitrag hat "
               "nur 1 bis 10 Wörter, eine Reaktion, ein Einwurf oder eine kurze Nachfrage. Die "
               "übrigen tragen den Inhalt und haben mindestens 40, höchstens 90 Wörter. Längen "
               "dazwischen sind selten.\n"
               "- Die Personen bauen eine Erklärung gemeinsam auf: Eine beginnt, die andere hakt "
               "nach, ergänzt oder zieht einen Schluss. Niemand hält einen Vortrag.\n"
               "- Beide Personen tragen Inhalt: Wer moderiert, erklärt auch selbst Teile, bringt "
               "Beispiele und eigene Beobachtungen ein. Wer fachlich erklärt, fragt auch mal "
               "zurück oder staunt. In jedem Teil erklärt jede Person mindestens drei Punkte "
               "selbst, mit 40 bis 90 Wörtern, und die andere reagiert, fragt nach oder ergänzt.\n"
               "- Persönlich: Die Personen sprechen sich ab und zu mit Namen an, wer spricht nennt "
               "nur den Namen der anderen Person, nie den eigenen. Sie zeigen, was "
               "sie überrascht, was sie bezweifeln oder was ihnen beim Lesen aufgefallen ist.\n")
            + f"- Im Schnitt etwa {je} Wörter je Beitrag, nie mehr als 150.\n"
            "- Wenige Punkte in der Tiefe statt einer Aufzählung: zu jeder Regel, warum es sie "
            "gibt, was aus ihr folgt und ein Beispiel aus dem Alltag der Hörer. Gern auch ein "
            "Einwand oder ein verbreiteter Irrtum, den die Antwort mit dem Material auflöst.\n"
            + _rahmen_de(teil, teile)
            + (f"- Nach der Begrüßung erzählt eine Person diese kleine Geschichte, lebendig und "
               f"in eigenen Worten, und das Gespräch greift ihre Frage auf: {opening}\n"
               if teil == 1 and opening else "")
            + ("- Vor der Verabschiedung kommt das große Bild, das alle Themen der Folge "
               "verbindet, und ein Gedanke, den die Hörer mitnehmen, gern als offene Frage"
               + (f": {thread}" if thread else "") + ".\n" if teil == teile else "")
            + ("- Wiederhole nichts, was bisher schon gesagt wurde.\n" if bisher else "")
            + (f"- Der letzte Beitrag bisher kam von speaker {bisher[-1].speaker}, dein erster "
               "Beitrag kommt von jemand anderem.\n" if bisher and not allein else "")
            + ("- Die Teile sind nur Arbeitsschritte. Für die Hörer ist es ein einziges "
               "Gespräch, erwähne nie einen Teil.\n" if teile > 1 else "")
            + "- Keine Regieanweisungen, keine Namen vor dem Text, keine Zwischenüberschriften.\n"
            "- Zahlen und Formeln ausschreiben, der Text wird vorgelesen.\n"
            "- Die Zeilen in eckigen Klammern im Material nennen nur Datei und Seite, lies sie nie vor.\n"
        )
    else:
        system = (
            "You write the script of a podcast episode for a university. "
            "Facts, figures, deadlines and conditions come only from the material provided and "
            "you add none. Examples, comparisons and objections you may bring yourself, so the "
            "matter becomes vivid. "
            "You answer with a JSON object of the form "
            '{"lines": [{"speaker": 0, "text": "..."}]} and nothing else.'
        )
        teilzeile = (f"You write part {teil} of {teile} of the episode.\n"
                     f"Plan of the whole episode:\n{plan}\n\n") if teile > 1 else ""
        aufgabe = (
            f"{teilzeile}Material:\n---\n{source}\n---\n\n"
            f"{_besprochen(besprochen, 'Already covered, do not repeat')}"
            f"{_bisher(bisher, params)}"
            f"Cast, the number is the value for speaker:\n{_besetzung(params)}\n\n"
            f"Style: {_STYLE_EN.get(params.style, params.style)}\n"
            f"Length: exactly {anzahl} contributions, {woerter} words in total, {je} per contribution on average.\n\n"
            "Rules:\n"
            "- Language of the script: English.\n"
            + ("- Only one person speaks, speaker is always 0.\n" if allein else
               "- The people take turns, nobody speaks twice in a row.\n"
               "- Every person appears and keeps their role.\n"
               "- Quick turns like a real conversation: about every third contribution has "
               "only 1 to 10 words, a reaction, an interjection or a short follow up question. "
               "The others carry the content and have at least 40, at most 90 words. Lengths in "
               "between are rare.\n"
               "- The people build an explanation together: one starts, the other asks back, "
               "adds to it or draws a conclusion. Nobody gives a lecture.\n"
               "- Both people carry content: whoever hosts also explains parts, brings examples "
               "and own observations. Whoever is the expert also asks back or is surprised. In "
               "every part each person explains at least three points themselves, with 40 to 90 "
               "words, and the other reacts, asks back or adds to it.\n"
               "- Personal: the people now and then address each other by name, the speaker only "
               "ever names the other person, never themselves. They show what "
               "surprises them, what they doubt or what struck them while reading.\n")
            + f"- About {je} words per contribution on average, never more than 150.\n"
            "- Few points in depth instead of a list: for each rule why it exists, what "
            "follows from it and an example from the listeners' everyday life. An objection or "
            "a common misconception that the answer clears up with the material is welcome.\n"
            + _rahmen_en(teil, teile)
            + (f"- After the greeting one person tells this small story, vividly and in their own "
               f"words, and the conversation takes up its question: {opening}\n"
               if teil == 1 and opening else "")
            + ("- Before the goodbye comes the big picture that connects all subjects of the "
               "episode, and one thought the listeners take home, maybe as an open question"
               + (f": {thread}" if thread else "") + ".\n" if teil == teile else "")
            + ("- Repeat nothing that was already said.\n" if bisher else "")
            + (f"- The last contribution so far was by speaker {bisher[-1].speaker}, your first "
               "contribution comes from someone else.\n" if bisher and not allein else "")
            + ("- The parts are only working steps. For the listeners it is one single "
               "conversation, never mention a part.\n" if teile > 1 else "")
            + "- No stage directions, no names before the text, no headings.\n"
            "- Spell out numbers and formulas, the text is read aloud.\n"
            "- The lines in square brackets in the material only name file and page, never read them out.\n"
        )
    aufgabe += glossar.block(params.glossary, params.language)
    aufgabe += anweisung.schreib_zusatz(params.instructions, params.instruction_way)
    return [{"role": "system", "content": system}, {"role": "user", "content": aufgabe}]


def plan_messages(material: str, modus: str, params: PodcastParams, teile: int,
                  dateien: list[str] | None = None,
                  fehlt: list[str] | None = None) -> list[dict]:
    """The episode laid out in parts, each with the passages it talks about."""
    from src.services.text_map import hinweis

    sprache = "German" if params.language == "de" else "English"
    # An instruction with a subject of its own decides what the episode is about, not the files.
    if anweisung.fokus(params.instructions, params.instruction_way):
        dateien = None
    system = (
        "You plan a podcast episode for university teaching. From the material you pick what "
        f"matters to the listeners and lay the episode out in exactly {teile} consecutive "
        "parts, each with its own subject. Order the parts by what affects the listeners most, "
        "and where documents touch the same subject bring them together, never one file after "
        "the other. Leave out administrative detail on how bodies are organised, elected, "
        "staffed or financed unless the material is mainly about that.\n"
        f"Write titles, gists, opening and thread in {sprache}.\n{hinweis(modus)}\n"
        + (f"The material comes from {len(dateien)} files: {', '.join(dateien)}. EVERY one of "
           "them is talked about in the episode.\n" if dateien and len(dateien) > 1 else "")
        + 'Answer with one JSON object only: {"opening": "...", "thread": "...", "parts": '
        '[{"title": "...", "gist": "...", "refs": [12, "14-17"]}]}. The opening is a '
        "small story: one person in one concrete situation from the listeners' own life that "
        "the material decides, ending in a question the episode answers, in two or three "
        "sentences, ideally touching several of the documents, never a list of problems. The thread is one "
        "sentence on what connects all documents, the thought the listeners take home. Both "
        "span the whole material, not the frame of the largest one. The gist is one sentence saying what that part covers and "
        "which question it answers."
    )
    aufgabe = f"/no_think\nMATERIAL:\n{material}\n"
    aufgabe += anweisung.plan_zusatz(params.instructions, params.instruction_way, "part")
    if fehlt:
        aufgabe += ("\nYOUR LAST PLAN GAVE THESE FILES FAR TOO LITTLE ROOM. Give each a "
                    "share of the episode that matches how much of the material it holds, "
                    "with parts about it by title: " + ", ".join(fehlt))
    return [{"role": "system", "content": system}, {"role": "user", "content": aufgabe}]


# A model sometimes copies the numbers into the gist, "... refs: [21-32]".
_REFS_IM_TEXT = re.compile(r"\s*\brefs?\s*:.*$", re.IGNORECASE)


def parse_plan(raw: str, stellen, teile: int) -> list[dict]:
    """The parts out of the planning answer, each with its passage numbers.

    Too many parts are folded into the last one, too few stay as they are: the episode
    is then written in fewer calls, each still small enough.
    """
    text = (raw or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ScriptUnusable("keine JSON-Klammern im Plan")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ScriptUnusable(f"kein gültiges JSON im Plan: {exc}") from exc
    roh = data.get("parts") if isinstance(data, dict) else None
    aus: list[dict] = []
    for eintrag in roh if isinstance(roh, list) else []:
        if not isinstance(eintrag, dict):
            continue
        titel = " ".join(str(eintrag.get("title") or "").split())[:120]
        nummern = stellen(eintrag.get("refs"))
        if not titel or not nummern:
            continue
        kern = _REFS_IM_TEXT.sub("", " ".join(str(eintrag.get("gist") or "").split()))
        aus.append({"title": titel, "gist": kern.strip()[:300], "stellen": nummern})
    if not aus:
        raise ScriptUnusable("der Plan enthält keinen Teil mit Stellen")
    while len(aus) > teile:
        letzter = aus.pop()
        aus[-1]["stellen"] = aus[-1]["stellen"] + [n for n in letzter["stellen"]
                                                   if n not in aus[-1]["stellen"]]
    for teil in aus:
        teil["opening"] = teil["thread"] = ""
    aus[0]["opening"] = " ".join(str(data.get("opening") or "").split())[:400]
    aus[-1]["thread"] = " ".join(str(data.get("thread") or "").split())[:300]
    return aus


def ohne_eigene_anrede(lines: list[Line], namen: list[str]) -> list[Line]:
    """A speaker never addresses themselves, a model that mixes up the cast does."""
    aus: list[Line] = []
    for line in lines:
        name = namen[line.speaker] if line.speaker < len(namen) else ""
        text = line.text
        if name:
            n = re.escape(name)
            text = re.sub(rf"^\s*{n}\s*[,!]\s*", "", text)
            text = re.sub(rf",\s*{n}\b(?=\s*[.!?,])", "", text)
            text = text[:1].upper() + text[1:]
        aus.append(line.model_copy(update={"text": text}) if text != line.text else line)
    return aus


class ScriptUnusable(RuntimeError):
    """The answer was not a usable script, the caller may try once more."""


def parse_answer(raw: str, person_count: int) -> list[Line]:
    """The model's answer to lines, with every rule checked that costs us later."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ScriptUnusable("keine JSON-Klammern in der Antwort")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ScriptUnusable(f"kein gültiges JSON: {exc}") from exc

    roh = data.get("lines") if isinstance(data, dict) else None
    if not isinstance(roh, list) or not roh:
        raise ScriptUnusable("die Antwort enthält keine Beiträge")

    lines: list[Line] = []
    for eintrag in roh[:PODCAST_MAX_LINES]:
        if not isinstance(eintrag, dict):
            continue
        inhalt = str(eintrag.get("text") or "").strip()
        if not inhalt:
            continue
        try:
            sprecher = int(eintrag.get("speaker", 0))
        except (TypeError, ValueError):
            sprecher = 0
        # Wrapped instead of clamped: a stray index must not collapse the conversation
        # onto one voice and take the whole script down with it.
        sprecher = sprecher % person_count if person_count else 0
        lines.append(Line(speaker=sprecher, text=inhalt[:PODCAST_MAX_LINE_CHARS]))

    if len(lines) < 2:
        raise ScriptUnusable(f"nur {len(lines)} brauchbare Beiträge")
    if person_count > 1 and len({l.speaker for l in lines}) < 2:
        raise ScriptUnusable("nur eine Person kommt vor, obwohl mehrere besetzt sind")
    logger.info("Podcast: {} Beiträge, {} Stimmen", len(lines), len({l.speaker for l in lines}))
    return lines


def rephrase_messages(line: Line, params: PodcastParams, nachbarn: list[str]) -> list[dict]:
    """One contribution said differently, the rest of the conversation stays put."""
    person = params.persons[line.speaker] if line.speaker < len(params.persons) else params.persons[0]
    rollen = _ROLE_DE if params.language == "de" else _ROLE_EN
    umfeld = "\n".join(nachbarn)
    if params.language == "de":
        system = ('Du formulierst einen einzelnen Podcast-Beitrag neu. Der Inhalt bleibt, '
                  'die Wortwahl ändert sich. Du antwortest mit einem JSON-Objekt der Form '
                  '{"text": "..."} und mit nichts sonst.')
        auftrag = (f"Sprecher: {person.name} ({rollen.get(person.role, person.role)})\n"
                   f"Umfeld im Gespräch:\n{umfeld}\n\n"
                   f"Dieser Beitrag soll neu formuliert werden:\n{line.text}\n\n"
                   "Gleiche Länge, gleiche Aussage, keine Anführungszeichen, keine Namensnennung "
                   "vor dem Text.")
    else:
        system = ('You rephrase a single podcast contribution. The content stays, the wording '
                  'changes. You answer with a JSON object of the form '
                  '{"text": "..."} and nothing else.')
        auftrag = (f"Speaker: {person.name} ({rollen.get(person.role, person.role)})\n"
                   f"Surrounding conversation:\n{umfeld}\n\n"
                   f"This contribution should be rephrased:\n{line.text}\n\n"
                   "Same length, same statement, no quotation marks, no name in front of the text.")
    auftrag += glossar.block(params.glossary, params.language)
    return [{"role": "system", "content": system}, {"role": "user", "content": auftrag}]


# How much of the material one reworking call carries along.
REFINE_SOURCE_CHARS = 4000


def _inhaltswoerter(text: str) -> set[str]:
    """Words from four letters on, without numbers and punctuation."""
    return {w for w in re.findall(r"[^\W\d_]{4,}", (text or "").lower())}


def source_excerpt(source: str, needles: list[str], limit: int) -> str:
    """The passages of the material that share words with the contribution."""
    if not source.strip() or limit <= 0:
        return ""
    absaetze = [a.strip() for a in re.split(r"\n\s*\n", source) if a.strip()]
    gesucht: set[str] = set()
    for needle in needles:
        gesucht |= _inhaltswoerter(needle)
    treffer = [(len(gesucht & _inhaltswoerter(a)), i, a) for i, a in enumerate(absaetze)]
    genommen: list[tuple[int, str]] = []
    laenge = 0
    for zahl, i, absatz in sorted(treffer, key=lambda t: (-t[0], t[1])):
        if zahl == 0:
            break
        if laenge + len(absatz) > limit:
            continue
        genommen.append((i, absatz))
        laenge += len(absatz) + 2
    if not genommen:
        # Nothing matched, so the beginning of the material is the honest guess.
        return source.strip()[:limit].strip()
    return "\n\n".join(absatz for _, absatz in sorted(genommen))


def _stelle_de(position: tuple[int, int] | None) -> str:
    """Where in the episode this contribution sits, the ends carry their own job."""
    if not position:
        return ""
    nummer, gesamt = position
    text = f"Stelle im Gespräch: Beitrag {nummer} von {gesamt}.\n"
    if nummer == 1:
        text += "Der erste Beitrag begrüßt und nennt das Thema.\n"
    elif nummer == gesamt:
        text += "Der letzte Beitrag verabschiedet.\n"
    return text + "\n"


def _stelle_en(position: tuple[int, int] | None) -> str:
    """Where in the episode this contribution sits, the ends carry their own job."""
    if not position:
        return ""
    nummer, gesamt = position
    text = f"Place in the conversation: contribution {nummer} of {gesamt}.\n"
    if nummer == 1:
        text += "The first contribution greets and names the topic.\n"
    elif nummer == gesamt:
        text += "The last contribution says goodbye.\n"
    return text + "\n"


def refine_messages(line: Line, params: PodcastParams, nachbarn: list[str], quelle: str,
                    verlauf: list[dict], markiert: str = "",
                    position: tuple[int, int] | None = None) -> list[dict]:
    """One contribution reworked to a wish, the facts stay inside the material."""
    person = params.persons[line.speaker] if line.speaker < len(params.persons) else params.persons[0]
    rollen = _ROLE_DE if params.language == "de" else _ROLE_EN
    umfeld = "\n".join(nachbarn)
    wunsch = next((m.get("content", "") for m in reversed(verlauf) if m.get("role") == "user"), "").strip()
    if params.language == "de":
        system = ("Du überarbeitest einen einzelnen Podcast-Beitrag nach dem Wunsch der Person. "
                  "Die Fakten kommen ausschließlich aus dem gelieferten Material, du erfindest nichts "
                  "dazu. Wortwahl, Ton und Didaktik sind frei. Du antwortest mit einem JSON-Objekt der "
                  'Form {"text": "..."} und mit nichts sonst.')
        austausch = "\n".join(
            f"{'Wunsch' if m.get('role') == 'user' else 'Vorschlag'}: {m.get('content', '')}"
            for m in verlauf[:-1]
        )
        auftrag = (f"Sprecher: {person.name} ({rollen.get(person.role, person.role)})\n\n"
                   f"Material:\n---\n{quelle}\n---\n\n"
                   f"Umfeld im Gespräch:\n{umfeld}\n\n")
        auftrag += _stelle_de(position)
        if line.text.strip():
            auftrag += f"Dieser Beitrag steht zur Überarbeitung:\n{line.text}\n\n"
        else:
            auftrag += ("Dieser Beitrag ist noch leer und soll geschrieben werden. Schreib nur "
                        "diesen einen Beitrag, nicht die Antwort darauf und nicht den Beitrag "
                        "einer anderen Person.\n\n")
        if markiert:
            auftrag += (f"Markierte Stelle im Beitrag:\n{markiert}\n\n"
                        "Antworte nur mit dem Text, der diese Stelle ersetzt.\n\n")
        if austausch:
            auftrag += f"Bisheriger Austausch:\n{austausch}\n\n"
        auftrag += (f"Wunsch: {wunsch}\n"
                    "Keine Anführungszeichen, keine Namensnennung vor dem Text.")
    else:
        system = ("You rework a single podcast contribution following the wish of the person. "
                  "The facts come only from the material provided, you invent nothing on top. "
                  "Wording, tone and didactics are free. You answer with a JSON object of the "
                  'form {"text": "..."} and nothing else.')
        austausch = "\n".join(
            f"{'Wish' if m.get('role') == 'user' else 'Suggestion'}: {m.get('content', '')}"
            for m in verlauf[:-1]
        )
        auftrag = (f"Speaker: {person.name} ({rollen.get(person.role, person.role)})\n\n"
                   f"Material:\n---\n{quelle}\n---\n\n"
                   f"Surrounding conversation:\n{umfeld}\n\n")
        auftrag += _stelle_en(position)
        if line.text.strip():
            auftrag += f"This contribution is up for reworking:\n{line.text}\n\n"
        else:
            auftrag += ("This contribution is still empty and should be written. Write only this "
                        "one contribution, not the answer to it and not the contribution of "
                        "another person.\n\n")
        if markiert:
            auftrag += (f"Selected passage inside the contribution:\n{markiert}\n\n"
                        "Answer only with the text that replaces this passage.\n\n")
        if austausch:
            auftrag += f"Conversation so far:\n{austausch}\n\n"
        auftrag += (f"Wish: {wunsch}\n"
                    "No quotation marks, no name in front of the text.")
    auftrag += glossar.block(params.glossary, params.language)
    return [{"role": "system", "content": system}, {"role": "user", "content": auftrag}]


def _aus_json(raw: str) -> str | None:
    """The answer comes in JSON mode, so the bare sentence sits in a wrapper."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return str(data.get("text") or "").strip() if isinstance(data, dict) else None


def clean_rephrased(raw: str, fallback: str) -> str:
    """A model likes to add a frame, only the bare sentence is wanted."""
    text = (_aus_json(raw) or raw).strip().strip('"').strip()
    if ":" in text[:40] and "\n" not in text[: text.find(":")]:
        kopf, rest = text.split(":", 1)
        if len(kopf.split()) <= 3:
            text = rest.strip()
    text = text[:PODCAST_MAX_LINE_CHARS].strip()
    return text or fallback
