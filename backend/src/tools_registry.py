# backend/src/tools_registry.py
"""The registry of the global tool keys, it has to match the toolbar."""

ALL_TOOL_KEYS: tuple[str, ...] = (
    "translation",
    "tts",
    "transcription",
    "image",
    "summary",
    "screencast",
    "glossary",
)
