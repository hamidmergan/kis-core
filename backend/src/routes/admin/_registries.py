"""Static configuration registries: system prompts, tool catalog, tool labels."""

from src.tool_prompts import (
    SCRIPT_BATCH_PREVIEW as _PROMPT_SCRIPT_BATCH_PREVIEW,
    SCRIPT_REFINE_DEFAULT as _PROMPT_SCRIPT_REFINE_DEFAULT,
    SUMMARY_DEFAULT as _PROMPT_SUMMARY_DEFAULT,
    IMAGE_ANALYZE_DEFAULT as _PROMPT_IMAGE_ANALYZE_DEFAULT,
    AIA_SYSTEM_DIRECT as _PROMPT_TUTOR_SYSTEM_DIRECT,
    AIA_SYSTEM_RAG as _PROMPT_TUTOR_SYSTEM_RAG,
    AIA_POPUP_ACTIONS as _TUTOR_POPUP_ACTIONS,
)

PROMPT_REGISTRY = [
    {
        "key": "prompt_script_batch",
        "label": "Screencast-Skripte (Batch-Modus)",
        "description": "Wird im Auto-Modus für parallele Batch-Verarbeitung genutzt. Enthält strukturelle Trennzeichen (|||) die der Parser erwartet - nicht editierbar.",
        "editable": False,
        "default": _PROMPT_SCRIPT_BATCH_PREVIEW,
    },
    {
        "key": "prompt_script_refine",
        "label": "Screencast-Skripte (Einzelfolie)",
        "description": "Wird in Schritt 5 verwendet wenn der Nutzer das KI-Symbol neben einer Folie klickt.",
        "editable": False,
        "default": _PROMPT_SCRIPT_REFINE_DEFAULT,
    },
    {
        "key": "prompt_summary",
        "label": "Zusammenfassung",
        "description": "Wird vom Zusammenfassungs-Tool verwendet. Platzhalter {language} wird zur Laufzeit durch die erkannte Sprache des Dokuments ersetzt - nicht entfernen.",
        "editable": False,
        "default": _PROMPT_SUMMARY_DEFAULT,
    },
    {
        "key": "prompt_image_analyze",
        "label": "Bild-Analyse",
        "description": "Anweisung für das Bild-Analyse-Tool (qwen3-omni Modell).",
        "editable": False,
        "default": _PROMPT_IMAGE_ANALYZE_DEFAULT,
    },
    {
        "key": "prompt_tutor_system_direct",
        "label": "KI-Assistent: System-Prompt (Popup-Aktionen)",
        "description": "System-Prompt für Popup-Aktionen (Kürzen, Umformulieren etc.) im KI-Assistent. Wird bei markiertem Text verwendet.",
        "editable": False,
        "default": _PROMPT_TUTOR_SYSTEM_DIRECT,
    },
    {
        "key": "prompt_tutor_system_rag",
        "label": "KI-Assistent: System-Prompt (Chat / RAG)",
        "description": "System-Prompt für den KI-Assistent-Chat mit Quellensuche (RAG). Steuert Quellenangaben und Halluzinationsverbot.",
        "editable": False,
        "default": _PROMPT_TUTOR_SYSTEM_RAG,
    },
    *[
        {
            "key": f"prompt_tutor_popup_{action['key']}",
            "label": f"KI-Assistent Popup: {action['label_de']}",
            "description": f"Prompt fuer die Popup-Aktion '{action['label_de']}' im KI-Assistent PDF-Viewer.",
            "editable": False,
            "default": action["prompt_de"],
        }
        for action in _TUTOR_POPUP_ACTIONS
    ],
]


TOOLS_CONFIG = [
    {"key": "screencast",      "label": "Screencast"},
    {"key": "translation",   "label": "Dokumentenübersetzung"},
    {"key": "tts",           "label": "Text in Sprache"},
    {"key": "transcription", "label": "Transkription"},
    {"key": "image",         "label": "Bild-KI"},
    {"key": "glossary",      "label": "Glossaries"},
    {"key": "summary",       "label": "Zusammenfassung"},
]


TOOL_LABELS = {
    "screencast_render": "Screencast",
    "screencast_translate": "Screencast-Übersetzung",
    "tts": "Text in Sprache",
    "translation": "Übersetzung",
    "transcription": "Transkription",
    "image_generate": "Bild-Generierung",
    "image_edit": "Bild-Bearbeitung",
    "image_analyze": "Bild-Analyse",
    "summary": "Zusammenfassung",
}


TOOL_LABELS_TUTOR = {
    "flashcards": "Flashcards",
    "karteikarten": "Karteikarten",
    "quiz": "Quiz",
    "lueckentext": "Lückentext",
    "vokabeltest": "Vokabeltest",
}


DEFAULT_DISABLED_TOOLS: set[str] = set()


def tools_matching_query(q: str) -> list[str]:
    """Return all tool keys whose label contains the query (case-insensitive)."""
    q_lower = q.lower()
    return [k for k, label in TOOL_LABELS.items() if q_lower in label.lower()]
