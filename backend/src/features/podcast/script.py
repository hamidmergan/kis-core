"""The model call that turns material into a conversation, and the check of its answer."""

import json

from loguru import logger

from src.features.podcast import glossary as glossar
from src.features.podcast.schemas import LENGTH_PLAN, Line, PodcastParams
from src.limits import PODCAST_MAX_LINES, PODCAST_MAX_LINE_CHARS

_ROLE_DE = {
    "host": "Moderation, führt durch die Folge und stellt die Fragen",
    "expert": "Fachperson, erklärt die Sache und bringt Beispiele",
    "student": "Studierende Person, fragt nach, wenn etwas unklar bleibt",
    "critic": "Kritische Stimme, benennt Grenzen und Einwände",
}
_ROLE_EN = {
    "host": "host, leads through the episode and asks the questions",
    "expert": "expert, explains the matter and brings examples",
    "student": "student, asks again when something stays unclear",
    "critic": "critical voice, names limits and objections",
}
_STYLE_DE = {
    "teaching": "erklärend, ruhig, Schritt für Schritt",
    "casual": "locker und gesprächig, auch mal ein Scherz",
    "interview": "Interview, kurze Fragen und ausführliche Antworten",
}
_STYLE_EN = {
    "teaching": "explanatory, calm, step by step",
    "casual": "casual and chatty, the odd joke is fine",
    "interview": "interview, short questions and long answers",
}


def _besetzung(params: PodcastParams) -> str:
    rollen = _ROLE_DE if params.language == "de" else _ROLE_EN
    return "\n".join(
        f"{i}: {p.name} ({rollen.get(p.role, p.role)})" for i, p in enumerate(params.persons)
    )


def build_messages(source: str, params: PodcastParams) -> list[dict]:
    """One call, the answer is a JSON object with the list of contributions."""
    anzahl, je = LENGTH_PLAN.get(params.length, LENGTH_PLAN["medium"])
    woerter = anzahl * je
    allein = len(params.persons) == 1
    if params.language == "de":
        system = (
            "Du schreibst das Skript einer Podcast-Folge für eine Hochschule. "
            "Du nutzt ausschließlich das gelieferte Material und erfindest nichts dazu. "
            "Du antwortest mit einem JSON-Objekt der Form "
            '{"lines": [{"speaker": 0, "text": "..."}]} und mit nichts sonst.'
        )
        aufgabe = (
            f"Material:\n---\n{source}\n---\n\n"
            f"Besetzung, die Zahl ist der Wert für speaker:\n{_besetzung(params)}\n\n"
            f"Stil: {_STYLE_DE.get(params.style, params.style)}\n"
            f"Umfang: genau {anzahl} Beiträge mit je etwa {je} Wörtern, zusammen rund {woerter} Wörter.\n\n"
            "Regeln:\n"
            "- Sprache des Skripts: Deutsch.\n"
            + ("- Es spricht nur eine Person, speaker ist immer 0.\n" if allein else
               "- Die Personen wechseln sich ab, niemand spricht zweimal hintereinander.\n"
               "- Jede Person kommt vor und behält ihre Rolle.\n")
            + f"- Ein Beitrag ist ein gesprochener Absatz von etwa {je} Wörtern, nie mehr als 90.\n"
            "- Der erste Beitrag begrüßt und nennt das Thema, der letzte verabschiedet.\n"
            "- Keine Regieanweisungen, keine Namen vor dem Text, keine Zwischenüberschriften.\n"
            "- Zahlen und Formeln ausschreiben, der Text wird vorgelesen.\n"
        )
    else:
        system = (
            "You write the script of a podcast episode for a university. "
            "You use only the material provided and invent nothing. "
            "You answer with a JSON object of the form "
            '{"lines": [{"speaker": 0, "text": "..."}]} and nothing else.'
        )
        aufgabe = (
            f"Material:\n---\n{source}\n---\n\n"
            f"Cast, the number is the value for speaker:\n{_besetzung(params)}\n\n"
            f"Style: {_STYLE_EN.get(params.style, params.style)}\n"
            f"Length: exactly {anzahl} contributions of about {je} words each, {woerter} words in total.\n\n"
            "Rules:\n"
            "- Language of the script: English.\n"
            + ("- Only one person speaks, speaker is always 0.\n" if allein else
               "- The people take turns, nobody speaks twice in a row.\n"
               "- Every person appears and keeps their role.\n")
            + f"- One contribution is one spoken paragraph of about {je} words, never more than 90.\n"
            "- The first contribution greets and names the topic, the last says goodbye.\n"
            "- No stage directions, no names before the text, no headings.\n"
            "- Spell out numbers and formulas, the text is read aloud.\n"
        )
    aufgabe += glossar.block(params.glossary, params.language)
    if params.instructions.strip():
        label = "Zusätzliche Anweisung" if params.language == "de" else "Additional instruction"
        aufgabe += f"\n{label}: {params.instructions.strip()}\n"
    return [{"role": "system", "content": system}, {"role": "user", "content": aufgabe}]


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
