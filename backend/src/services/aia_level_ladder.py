"""The one source for what makes up a language level."""

import json

# The level ladder in fixed order.
LEVELS: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")

# Admin setting from level to description, empty means default.
LEVEL_DESCRIPTIONS_SETTING = "language_diagnosis_level_descriptions_de"

# German, because a language expert reads and writes it in the admin area.
DEFAULT_LEVEL_DESCRIPTIONS: dict[str, str] = {
    "A1": "Einzelne Wörter und auswendig gelernte Sätze, nur Gegenwart. Die Verständigung bricht oft ab.",
    "A2": "Einfache Hauptsätze über den Alltag, Vergangenheit wird versucht und oft falsch. Sehr kleiner Wortschatz.",
    "B1": "Zusammenhängende Sätze mit Nebensatz, kommt mit bekannten Themen zurecht. Fehler stören das Verstehen nicht.",
    "B2": "Klare, ausführliche Sprache über viele Themen, kann einen Standpunkt begründen. Fehler stören selten.",
    "C1": "Fließend und spontan, komplexe Strukturen wie selbstverständlich, treffende und idiomatische Wortwahl.",
    "C2": "Fast muttersprachliche Genauigkeit und Bandbreite, volle Kontrolle über Ton und Nuance, nur die feinsten Ausrutscher.",
}


def parse_level_descriptions(raw: str) -> dict:
    """The admin descriptions, merged onto the defaults."""
    descriptions = dict(DEFAULT_LEVEL_DESCRIPTIONS)
    if not raw or not raw.strip():
        return descriptions
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return descriptions
    if not isinstance(data, dict):
        return descriptions
    for level in LEVELS:
        value = data.get(level)
        if isinstance(value, str) and value.strip():
            descriptions[level] = value.strip()
    return descriptions


def build_levels_block(descriptions: dict) -> str:
    """The descriptions as a bullet list, one line per level."""
    lines = []
    for level in LEVELS:
        text = (descriptions.get(level) or "").strip()
        if text:
            lines.append(f"- {level}: {text}")
    return "\n".join(lines)


def description_for_level(level: str | None, descriptions: dict) -> str:
    """The description of a learner's one level, empty otherwise."""
    if not level:
        return ""
    return (descriptions.get(level) or "").strip()


def resolve_prompt_setting(stored: str | None, legacy: str, default: str) -> str:
    """Stored prompt text, the old default counts as not set."""
    text = (stored or "").strip()
    if not text or text == legacy.strip():
        return default
    return text
