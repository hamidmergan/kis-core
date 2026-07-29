"""Katalog der Grammatik-Aufgabentypen.

Ein Aufgabentyp ist reine Konfiguration: Anweisung und Regel wandern in den
Generier-Prompt, das Label in die Oberfläche. Ein neuer Typ ist deshalb ein
weiterer Eintrag in ``GRAMMAR_TYPES`` und braucht weder neuen Prompt-Code noch
eine eigene Komponente im Frontend.

Liegt bewusst unter ``services`` und nicht bei den Celery-Tasks: Routen, Task und
Prüfung brauchen ihn gleichermassen, und ein Import aus ``tasks`` heraus zieht das
ganze Task-Paket nach und schliesst einen Importzyklus über die Attribution.

``format`` entscheidet, wie geantwortet wird: "text" ist Freitext und wird
serverseitig geprüft, "choice" ist Ankreuzen und wird im Browser entschieden.
Ein Ankreuz-Typ bringt zusätzlich ``wrong`` und ``example_task`` mit, beides nur
für das Muster im Prompt.
"""

from typing import Optional

# Reihenfolge ist die Anzeigereihenfolge im Erstellen-Dialog. Der erste Eintrag ist
# im Dialog vorausgewählt, deshalb steht das Quiz vorne: Set anlegen bleibt ein Klick.
GRAMMAR_TYPES: list[dict] = [
    {
        "id": "grammar_quiz",
        "label": {"de": "Grammatik-Quiz", "en": "Grammar quiz"},
        "instruction": {
            "de": "Kreuze die richtige Form an.",
            "en": "Tick the correct form.",
        },
        # Der einzige Typ ohne feste Zielform: welche Formen drankommen, entscheidet
        # das Modell am Quelltext. Deshalb trägt hier jede Aufgabe ihre eigene
        # Anweisung, statt eines Musterpaars über dem ganzen Set.
        "rule": (
            "Each exercise shows one statement about the source subject matter and asks the "
            "learner to produce ONE specific grammatical form of it. Choose the forms yourself "
            "from what the output language offers (voice, tense, mood, case, comparison, modal "
            "verbs, word order). Use at least three different forms across the set and never "
            "the same one in two exercises in a row: told only to vary, the model drills a "
            "single form. The required form is named in 'task', never in the options.\n"
            "NEVER ask the learner to join two sentences with a conjunction. That is not a "
            "form exercise: the conjunction has to fit the meaning, and a wrong one turns the "
            "sentence into nonsense. Every exercise transforms ONE given sentence."
        ),
        "example": {
            "de": {"before": "Die Dozentin erklärt einen komplizierten Begriff.",
                   "after": "Ein komplizierter Begriff wird von der Dozentin erklärt."},
            "en": {"before": "The lecturer explains a complicated term.",
                   "after": "A complicated term is explained by the lecturer."},
        },
        "example_task": {
            "de": "Bilden Sie das Passiv Präsens.",
            "en": "Form the present passive.",
        },
        # Zwei weitere fertige Aufgaben. Ein einziges Beispiel reicht nicht: auf
        # Vorlesungsmaterial lieferte das Modell damit 0 und 2 von 10 brauchbaren
        # Aufgaben, mit dreien 4 und 7. Es ahmt Formvarianten nach, die es sieht, und
        # ein Grammatik-Handout liefert selbst Dutzende. Genau deshalb sah das Werkzeug
        # auf einem Handout gut aus und versagte auf jeder Fachquelle.
        "more_examples": {
            "de": [
                {"task": "Bilden Sie das Perfekt.",
                 "sentence": "Das Team sammelt die Daten.",
                 "options": ["Das Team hat die Daten gesammelt.",
                             "Das Team ist die Daten gesammelt.",
                             "Das Team hat die Daten sammeln.",
                             "Das Team hatte die Daten gesammelt."]},
                {"task": "Bilden Sie den Satz mit 'müssen'.",
                 "sentence": "Die Studierenden prüfen die Quellen.",
                 "options": ["Die Studierenden müssen die Quellen prüfen.",
                             "Die Studierenden müssen die Quellen geprüft.",
                             "Die Studierenden müsst die Quellen prüfen.",
                             "Die Studierenden müssen die Quellen zu prüfen."]},
            ],
            "en": [
                {"task": "Form the present perfect.",
                 "sentence": "The team collects the data.",
                 "options": ["The team has collected the data.",
                             "The team is collected the data.",
                             "The team has collect the data.",
                             "The team had collected the data."]},
                {"task": "Rewrite the sentence with 'must'.",
                 "sentence": "The students check the sources.",
                 "options": ["The students must check the sources.",
                             "The students must checked the sources.",
                             "The students must to check the sources.",
                             "The students musts check the sources."]},
            ],
        },
        # Die drei falschen Formen zum Musterpaar. Ohne sie hat das Modell kein
        # Beispiel dafür, wie ein Distraktor aussieht, und erfindet inhaltliche
        # Optionen: genau der gemeldete Fehler.
        "wrong": {
            "de": [
                "Ein komplizierter Begriff ist von der Dozentin erklärt.",
                "Ein komplizierter Begriff wird von der Dozentin erklären.",
                "Ein komplizierter Begriff wurde von der Dozentin erklärt.",
            ],
            "en": [
                "A complicated term is explain by the lecturer.",
                "A complicated term was explained by the lecturer.",
                "A complicated term has explained by the lecturer.",
            ],
        },
        "format": "choice",
    },
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


def wrong_forms(entry: dict, locale: str) -> list[str]:
    """Die falschen Formen zum Musterpaar eines Ankreuz-Typs, sonst leer."""
    forms = entry.get("wrong") or {}
    return list(forms.get(locale) or forms.get(_FALLBACK_LANG) or [])


def worked_exercises(entry: dict, locale: str) -> list[dict]:
    """Alle fertigen Beispielaufgaben eines Ankreuz-Typs, das Musterpaar zuerst.

    Jede als ``{"task", "sentence", "options"}``. Der Generator zeigt sie hinter dem
    Quellmaterial, weil ein einziges Beispiel nachweislich nicht reicht.
    """
    pair = example_pair(entry, locale)
    if not pair["before"]:
        return []
    first = {
        "task": localized(entry, "example_task", locale),
        "sentence": pair["before"],
        "options": [pair["after"], *wrong_forms(entry, locale)],
    }
    more = entry.get("more_examples") or {}
    extra = more.get(locale) or more.get(_FALLBACK_LANG) or []
    return [first, *[dict(e) for e in extra]]


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
    "wrong_forms",
    "worked_exercises",
    "catalog_for_api",
]
