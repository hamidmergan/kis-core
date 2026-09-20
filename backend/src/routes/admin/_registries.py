"""Static configuration registries: tool catalog, tool labels."""

TOOLS_CONFIG = [
    {"key": "screencast",      "label": "Screencast"},
    {"key": "podcast",       "label": "Podcast"},
    {"key": "praesentation", "label": "Präsentation"},
    {"key": "translation",   "label": "Dokumentenübersetzung"},
    {"key": "interpreter",   "label": "Dolmetscher"},
    {"key": "tts",           "label": "Text in Sprache"},
    {"key": "transcription", "label": "Transkription"},
    {"key": "image",         "label": "Bild-KI"},
    {"key": "glossary",      "label": "Glossaries"},
    {"key": "summary",       "label": "Zusammenfassung"},
]


TOOL_LABELS = {
    "screencast_render": "Screencast",
    "screencast_translate": "Screencast",
    "podcast": "Podcast",
    "praesentation": "Präsentation",
    "tts": "Text in Sprache",
    "translation": "Übersetzung",
    "transcription": "Transkription",
    "image_generate": "Bild-Generierung",
    "image_edit": "Bild-Bearbeitung",
    "image_analyze": "Bild-Analyse",
    "summary": "Zusammenfassung",
}


DEFAULT_DISABLED_TOOLS: set[str] = set()


def tools_matching_query(q: str) -> list[str]:
    """Return all tool keys whose label contains the query (case-insensitive)."""
    q_lower = q.lower()
    return [k for k, label in TOOL_LABELS.items() if q_lower in label.lower()]
