# backend/src/tools_registry.py
"""Canonical registry of global tool keys.

Mirrors the frontend ToolsSidebar TOOLS array. When adding a new global tool,
update both lists.
"""

ALL_TOOL_KEYS: tuple[str, ...] = (
    "translation",
    "tts",
    "transcription",
    "image",
    "summary",
    "screencast",
    "glossary",
)
