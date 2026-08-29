"""Ob ein Werkzeug global freigegeben ist, unabhaengig vom Recht einer Person."""

import json

from src import database as db

# Erst beim ersten Gebrauch geladen, sonst entsteht ein Ringbezug zur Admin-Verwaltung.
DEFAULT_DISABLED_TOOLS: set[str] | None = None


def is_released(tool_key: str, disabled: set[str], overrides: set[str]) -> bool:
    """Ohne Datenbank pruefbar, laedt die Standardliste beim ersten Aufruf einmalig nach."""
    global DEFAULT_DISABLED_TOOLS
    if DEFAULT_DISABLED_TOOLS is None:
        from src.routes.admin._registries import DEFAULT_DISABLED_TOOLS as _loaded
        DEFAULT_DISABLED_TOOLS = _loaded
    if tool_key in disabled:
        return False
    if tool_key in DEFAULT_DISABLED_TOOLS and tool_key not in overrides:
        return False
    return True


def read_release_state() -> tuple[set[str], set[str]]:
    """Die beiden Listen aus den Einstellungen."""
    disabled = set(json.loads(db.get_setting("disabled_tools", "[]")))
    overrides = set(json.loads(db.get_setting("enabled_tools_override", "[]")))
    return disabled, overrides


def is_released_now(tool_key: str) -> bool:
    """Die Frage mit dem aktuellen Stand aus der Datenbank."""
    disabled, overrides = read_release_state()
    return is_released(tool_key, disabled, overrides)
