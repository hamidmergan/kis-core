"""Wortschatz-Lückentext aus Quelltext (tool='wortschatz').

Ein Set ist genau EINE Aufgabe: ein zusammenhängender Text mit Platzhaltern, die
Lösungen und Grundformen hängen in ``extras.gaps`` daran. Der Text entsteht aus
dem Inhalt der Quellen und nicht aus der Luft, damit das Geübte zu dem passt, was
im Kurs gelesen wird.

Die Wörter kommen entweder aus den Quellen oder aus einem Lernkarten-Set. Im
zweiten Fall steht die Kartenliste im Auftrag, und ``clean_gaps`` wirft alles
weg, was nicht darauf steht.

Es gibt so viele Chips wie Lücken. Ablenker wurden ausdrücklich verworfen: wer
aus einem Lernkarten-Set übt, will genau diese Karten üben.
"""

import json
import re

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.services.aia_grammar_check import normalize

from src.features.ai_assistant.tasks.language_training._attribution import (
    PAGE_RULE,
    attach_chips_cited,
)
from src.features.ai_assistant.tasks.language_training._context import QuelleContext


_PLACEHOLDER_RE = re.compile(r"\{\{(\d+)\}\}")

# Unter diesem Anteil brauchbarer Lücken gilt der Durchlauf als misslungen. Lieber
# ein fehlgeschlagenes Set als ein Text, in dem die Hälfte der Lücken schon
# ausgefüllt dasteht. Derselbe Massstab wie in _source_grammar.py.
_MIN_USABLE_RATIO = 0.5

_SHAPE = (
    'Respond ONLY with a JSON object:\n'
    '{"title": "Short topic title", '
    '"instruction": "What the learner has to do, one or two sentences", '
    '"example": {"gapped": "A short sentence with ___ and the base form in brackets", '
    '"solved": "the word that belongs in that gap"}, '
    '"text": "A coherent passage where the target words are replaced by {{1}}, {{2}}, ...", '
    '"page": 12, '
    '"gaps": [{"base": "the dictionary form of the word", '
    '"solution": "the form that belongs in that gap"}]}\n'
)

_RULES = (
    "RULES:\n"
    "- The passage is ONE coherent text about the source content, not a list of "
    "unrelated sentences. It must read as if it came from the material.\n"
    "- Number the placeholders {{1}}, {{2}} and so on, without gaps, in the order "
    "they appear. The gaps array is in the same order.\n"
    "- Mix the forms: some gaps take the dictionary form unchanged, others need it "
    "inflected. The learner has to decide, that is the exercise.\n"
    "- Never use the same base word twice.\n"
    "- Never write a solution somewhere else in the passage, that gives it away.\n"
    "- 'base' is always the plain dictionary form, that is what the learner sees.\n"
    "- The instruction must say that some words keep their form and others do not.\n"
    "- The example must be about different material than the passage.\n"
)


def placeholders(text: str) -> list[int]:
    """Die Platzhalter-Nummern in der Reihenfolge, in der sie im Text stehen."""
    return [int(m.group(1)) for m in _PLACEHOLDER_RE.finditer(text or "")]


def _is_usable(gap: dict, words: list[str] | None, gesehen: set[str]) -> bool:
    """Ob diese Lücke stehen bleiben darf.

    Eine Lücke ohne Lösung ist unlösbar, eine doppelte Grundform stünde zweimal
    als Chip unter dem Text, und bei Lernkarten gehört alles weg, was nicht auf
    einer Karte steht.
    """
    base = (gap.get("base") or "").strip()
    solution = (gap.get("solution") or "").strip()
    if not base or not solution:
        return False
    schluessel = normalize(base)
    if not schluessel or schluessel in gesehen:
        return False
    if words is not None and schluessel not in {normalize(w) for w in words}:
        return False
    return True


def clean_gaps(text: str, gaps: list[dict], words: list[str] | None):
    """Unbrauchbare Lücken füllen, die brauchbaren neu durchnummerieren.

    Eine verworfene Lücke wird im Text durch ihre Lösung ersetzt statt gelöscht.
    Sonst risse ein Satz auseinander, und der Lernende bekäme einen Text, der
    mitten im Wort aufhört. Fehlt auch die Lösung, bleibt an der Stelle nichts.

    Gibt (Text, Lücken) zurück. Die Nummern laufen danach wieder lückenlos von 1.
    """
    gesehen: set[str] = set()
    behalten: list[dict] = []
    ersatz: dict[int, str] = {}
    for i, gap in enumerate(gaps or [], start=1):
        if _is_usable(gap, words, gesehen):
            gesehen.add(normalize(gap["base"]))
            behalten.append({"base": gap["base"].strip(),
                             "solution": gap["solution"].strip()})
            ersatz[i] = "{{%d}}" % len(behalten)
        else:
            ersatz[i] = (gap.get("solution") or "").strip()
    neu = _PLACEHOLDER_RE.sub(lambda m: ersatz.get(int(m.group(1)), ""), text or "")
    return neu, behalten


def _solved(text: str, gaps: list[dict]) -> str:
    """Die Musterlösung: derselbe Text mit eingesetzten Lösungen."""
    return _PLACEHOLDER_RE.sub(
        lambda m: gaps[int(m.group(1)) - 1]["solution"] if 0 < int(m.group(1)) <= len(gaps) else "",
        text,
    )


def _build_prompt(count: int, language: str, words: list[str] | None) -> str:
    kopf = (
        f"You write a vocabulary gap-fill exercise from the given source text. "
        f"Write the passage, the instruction and the example in {language}, "
        f"regardless of the source-text language.\n\n"
    )
    auftrag = f"Create a passage with exactly {count} gaps.\n\n"
    if words:
        liste = ", ".join(words)
        auftrag += (
            "Use ONLY these words as the gaps, nothing else. Every gap's 'base' must "
            f"be one of them, spelled exactly as given:\n{liste}\n\n"
        )
    else:
        auftrag += (
            "Pick the words yourself: the technical terms of the source material, the "
            "ones a learner of the subject has to know.\n\n"
        )
    return kopf + auftrag + _SHAPE + _RULES + PAGE_RULE


def generate_cloze_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    words: list[str] | None = None,
    locale: str = "de",
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
):
    """Ein Aufruf, ein Text, eine Aufgabe.

    Gibt ``(items, title)`` zurück oder ``None``, wenn nichts Brauchbares herauskam.
    ``items`` hat genau einen Eintrag.

    Es gibt kein ``coverage`` und keinen Abschnitts-Anteil wie bei den anderen
    Werkzeugen. Die Aufteilung auf alle Abschnitte zerschnitte den Text, und einer,
    der aus jedem Kapitel einen Satz nimmt, ist kein zusammenhängender Text mehr.
    """
    prompt = _build_prompt(count, language, words) + adaptive_suffix + title_avoidance
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Write the output in {language}.\n\n"
                                    f"Sources:\n\n{ctx.context}"},
    ]
    try:
        response = client.chat.completions.create(model=model, messages=messages,
                                                  temperature=0.6)
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
    except Exception as e:  # noqa: BLE001
        logger.warning("KI Tutor: Lückentext nicht lesbar: {}", e)
        return None
    if not isinstance(data, dict):
        return None

    text, gaps = clean_gaps(data.get("text") or "", data.get("gaps") or [], words)
    bestellt = max(1, count)
    if not gaps or len(gaps) < bestellt * _MIN_USABLE_RATIO:
        logger.warning("KI Tutor: Lückentext hatte nur {} von {} brauchbaren Lücken",
                       len(gaps), bestellt)
        return None

    beispiel = data.get("example") or {}
    item = {
        "front": text,
        "back": _solved(text, gaps),
        # Anweisung und Beispiel stehen HIER und nicht in den Set-Spalten
        # instruction/pattern_*, die die Grammatik-Übung benutzt. Der Vorrat trägt
        # Aufgaben und keine Set-Spalten: ein Text aus dem Vorrat käme sonst ohne
        # Anweisung an, und der Lernende sähe Lücken ohne zu wissen, was zu tun ist.
        "extras": {
            "gaps": gaps,
            "instruction": (data.get("instruction") or "").strip(),
            "example": {"gapped": (beispiel.get("gapped") or "").strip(),
                        "solved": (beispiel.get("solved") or "").strip()},
        },
        # Mit Unterstrich, weil _attribution.py genau dieses Feld liest (_cited_chip
        # prüft item.get("_page")). Ohne ihn griffe die erste Stufe der Zuordnung nie,
        # jeder Lauf zahlte die Suche, obwohl das Modell die Seite schon genannt hat.
        "_page": data.get("page"),
    }
    # Ein Text, ein Satz Quellen-Chips. Der Lückentext ist aus dem Material NEU
    # geschrieben und findet sich deshalb oft nicht wörtlich wieder, darum die
    # gestaffelte Zuordnung: erst die Seite, die das Modell selbst genannt hat (kostenlos,
    # kein Suchaufruf), dann die Suche, dann wenigstens die Datei. attach_chips_cited
    # entfernt _page nach dem Lesen selbst, hier bleibt nichts mehr aufzuräumen.
    attach_chips_cited([item], [item["back"]], ctx)

    title = (data.get("title") or "").strip() or ctx.multi_label
    return [item], title


__all__ = ["clean_gaps", "generate_cloze_from_source", "placeholders"]
