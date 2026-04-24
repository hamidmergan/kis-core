"""Statische Konfigurations-Registries: System-Prompts, Tool-Katalog, Tool-Labels."""

from src.tool_prompts import (
    SCRIPT_BATCH_PREVIEW as _PROMPT_SCRIPT_BATCH_PREVIEW,
    SCRIPT_REFINE_DEFAULT as _PROMPT_SCRIPT_REFINE_DEFAULT,
    SUMMARY_DEFAULT as _PROMPT_SUMMARY_DEFAULT,
    IMAGE_ANALYZE_DEFAULT as _PROMPT_IMAGE_ANALYZE_DEFAULT,
    KIA_SYSTEM_DIRECT as _PROMPT_TUTOR_SYSTEM_DIRECT,
    KIA_SYSTEM_RAG as _PROMPT_TUTOR_SYSTEM_RAG,
    KIA_POPUP_ACTIONS as _TUTOR_POPUP_ACTIONS,
    KIA_SUMMARY_PAGE_SYSTEM as _PROMPT_TUTOR_SUMMARY_PAGE_SYSTEM,
    KIA_SUMMARY_PAGE_USER_SMALL as _PROMPT_TUTOR_SUMMARY_PAGE_USER_SMALL,
    KIA_SUMMARY_PAGE_USER_LARGE as _PROMPT_TUTOR_SUMMARY_PAGE_USER_LARGE,
    KIA_SUMMARY_PAGE_BATCH_USER as _PROMPT_TUTOR_SUMMARY_PAGE_BATCH_USER,
)

PROMPT_REGISTRY = [
    {
        "key": "prompt_script_batch",
        "label": "Screencast-Skripte (Batch-Modus)",
        "description": "Wird im Auto-Modus für parallele Batch-Verarbeitung genutzt. Enthält strukturelle Trennzeichen (|||) die der Parser erwartet – nicht editierbar.",
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
        "description": "Wird vom Zusammenfassungs-Tool verwendet. Platzhalter {format} wird zur Laufzeit durch die gewählte Ausgabeformat-Anweisung ersetzt – nicht entfernen.",
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
    {
        "key": "prompt_tutor_summary_page_system",
        "label": "KI-Assistent: Seitenzusammenfassung System",
        "description": "System-Prompt für Seitenzusammenfassungen (alle Modelle). Platzhalter {lang}.",
        "editable": False,
        "default": _PROMPT_TUTOR_SUMMARY_PAGE_SYSTEM,
    },
    {
        "key": "prompt_tutor_summary_page_user_small",
        "label": "KI-Assistent: Seitenzusammenfassung User (kleine Modelle)",
        "description": "User-Prompt mit Platzhaltern {lang} und {content}. Enthält /no_think für qwen3.",
        "editable": False,
        "default": _PROMPT_TUTOR_SUMMARY_PAGE_USER_SMALL,
    },
    {
        "key": "prompt_tutor_summary_page_user_large",
        "label": "KI-Assistent: Seitenzusammenfassung User (große Modelle)",
        "description": "User-Prompt für große Modelle. Platzhalter {content}.",
        "editable": False,
        "default": _PROMPT_TUTOR_SUMMARY_PAGE_USER_LARGE,
    },
    {
        "key": "prompt_tutor_summary_page_batch_user",
        "label": "KI-Assistent: Seitenzusammenfassung User (Batch, große Modelle)",
        "description": "User-Prompt für Batch-Verarbeitung (mehrere Seiten pro Request). Platzhalter {n} und {pages}.",
        "editable": False,
        "default": _PROMPT_TUTOR_SUMMARY_PAGE_BATCH_USER,
    },
    *[
        {
            "key": f"prompt_tutor_popup_{action['key']}",
            "label": f"KI-Assistent Popup: {action['label']}",
            "description": f"Prompt fuer die Popup-Aktion '{action['label']}' im KI-Assistent PDF-Viewer.",
            "editable": False,
            "default": action["prompt"],
        }
        for action in _TUTOR_POPUP_ACTIONS
    ],
]


TOOLS_CONFIG = [
    {"key": "screencast",      "label": "Screencast"},
    {"key": "screencast-demo", "label": "Screencast-Demo"},
    {"key": "translation",   "label": "Dokumentenübersetzung"},
    {"key": "tts",           "label": "Text in Sprache"},
    {"key": "transcription", "label": "Transkription"},
    {"key": "image",         "label": "Bild-KI"},
    {"key": "glossary",      "label": "Glossare"},
    {"key": "summary",       "label": "Zusammenfassung"},
]


TOOL_LABELS = {
    "screencast_demo_render": "Demo-Screencast",
    "screencast_render": "Screencast",
    "screencast_translate": "Screencast-Übersetzung",
    "screencast_auto": "Screencast (Auto)",
    "tts": "Text in Sprache",
    "translation": "Übersetzung",
    "transcription": "Transkription",
    "image_generate": "Bild-Generierung",
    "image_edit": "Bild-Bearbeitung",
    "image_analyze": "Bild-Analyse",
    "summary": "Zusammenfassung",
}


TOOL_LABELS_TUTOR = {
    "lernkarten": "Lernkarten",
    "karteikarten": "Karteikarten",
    "quiz": "Quiz",
    "lueckentext": "Lückentext",
    "vokabeltest": "Vokabeltest",
}


DEFAULT_DISABLED_TOOLS: set[str] = set()


def tools_matching_query(q: str) -> list[str]:
    """Liefert alle Tool-Keys, deren Label den Query enthält (case-insensitive)."""
    q_lower = q.lower()
    return [k for k, label in TOOL_LABELS.items() if q_lower in label.lower()]
