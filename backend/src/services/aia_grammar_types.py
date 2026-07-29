"""Katalog der Grammatik-Aufgabentypen.

Ein Aufgabentyp ist reine Konfiguration: Anweisung und Regel wandern in den
Generier-Prompt, das Label in die Oberfläche. Ein neuer Typ ist deshalb ein
weiterer Eintrag in ``GRAMMAR_TYPES`` und braucht weder neuen Prompt-Code noch
eine eigene Komponente im Frontend.

Liegt bewusst unter ``services`` und nicht bei den Celery-Tasks: Routen, Task und
Prüfung brauchen ihn gleichermassen, und ein Import aus ``tasks`` heraus zieht das
ganze Task-Paket nach und schliesst einen Importzyklus über die Attribution.

``format`` ist heute überall "text" (Freitext). Ein späterer Multiple-Choice-Typ
setzt "choice" und lässt den Generator zusätzlich Distraktoren liefern.
"""

from typing import Optional

# Reihenfolge ist die Anzeigereihenfolge im Erstellen-Dialog.
GRAMMAR_TYPES: list[dict] = [
    {
        "id": "passive_present",
        "label": {"de": "Passiv Präsens", "en": "Passive present"},
        # Wortlaut vom Sprachenzentrum, wie auf dem Papier-Arbeitsblatt. Die Anweisung
        # nennt die Zielform nicht, sie zeigt sie: darunter steht das Musterpaar.
        "instruction": {
            "de": "Bitte transformiere nach folgendem Muster:",
            "en": "Please transform according to the following pattern:",
        },
        # Die Regel geht ausschliesslich an das Modell, der Lernende sieht sie nicht.
        "rule": (
            "Input: an active sentence in the present tense. "
            "Output: the same statement in the passive voice, present tense "
            "('werden' + past participle in German, 'to be' + past participle in English). "
            "The original subject becomes the agent ('von ...' / 'by ...') when it carries "
            "information, and is dropped when it is an empty subject such as 'man' or 'one'."
        ),
        # Musterpaar. Zwei Aufgaben: es steuert als Beispiel den Generier-Call
        # (Regeln allein ignoriert das Modell und liefert dann Quizfragen), und es
        # ist der Rückfall, wenn der Call kein eigenes Muster mitliefert.
        "example": {
            "de": {"before": "Hilde erklärt einen komplizierten Begriff.",
                   "after": "Ein komplizierter Begriff wird von Hilde erklärt."},
            "en": {"before": "Hilde explains a complicated term.",
                   "after": "A complicated term is explained by Hilde."},
        },
        "format": "text",
    },
    {
        "id": "passive_modal",
        "label": {"de": "Passiv mit Modalverb", "en": "Passive with modal verb"},
        "instruction": {
            "de": "Bitte transformiere nach folgendem Muster:",
            "en": "Please transform according to the following pattern:",
        },
        "rule": (
            "Input: an active sentence containing a modal verb (müssen, sollen, dürfen, "
            "können / must, should, may, can). "
            "Output: the same statement in the passive voice. The modal verb stays and keeps "
            "its person, the full verb becomes past participle + 'werden' (German) or "
            "'be' + past participle (English). The original subject becomes an optional agent."
        ),
        "example": {
            "de": {"before": "Ich muss die Briefe zur Post bringen.",
                   "after": "Die Briefe müssen (von mir) zur Post gebracht werden."},
            "en": {"before": "I must take the letters to the post office.",
                   "after": "The letters must be taken to the post office (by me)."},
        },
        "format": "text",
    },
]

_FALLBACK_LANG = "en"


def get_grammar_type(type_id: Optional[str]) -> Optional[dict]:
    """Katalog-Eintrag zu einer id, oder None wenn es die id nicht gibt."""
    if not type_id:
        return None
    for entry in GRAMMAR_TYPES:
        if entry["id"] == type_id:
            return entry
    return None


def localized(entry: dict, field: str, locale: str) -> str:
    """Feld eines Eintrags in der Oberflächensprache, mit Rückfall auf Englisch."""
    value = entry.get(field) or {}
    if isinstance(value, str):
        return value
    return value.get(locale) or value.get(_FALLBACK_LANG) or next(iter(value.values()), "")


def example_pair(entry: dict, locale: str) -> dict:
    """Das Musterpaar eines Typs als ``{"before": ..., "after": ...}``."""
    examples = entry.get("example") or {}
    pair = examples.get(locale) or examples.get(_FALLBACK_LANG) or {}
    return {"before": pair.get("before", ""), "after": pair.get("after", "")}


def catalog_for_api(locale: str) -> list[dict]:
    """Was das Frontend braucht: id, Label und Anweisung, ohne die Modell-Regel.

    Es gibt bewusst keine Auswahl pro Workspace: der Katalog ist überall derselbe,
    der Lernende wählt im Erstellen-Dialog.
    """
    return [
        {
            "id": e["id"],
            "label": localized(e, "label", locale),
            "instruction": localized(e, "instruction", locale),
            "format": e.get("format", "text"),
        }
        for e in GRAMMAR_TYPES
    ]


__all__ = [
    "GRAMMAR_TYPES",
    "get_grammar_type",
    "localized",
    "example_pair",
    "catalog_for_api",
]
