"""Whether a tool is released globally, independent of a person's permission."""

import json

from src import database as db

# Loaded on first use, else a circular import to the admin management arises.
DEFAULT_DISABLED_TOOLS: set[str] | None = None


def is_released(tool_key: str, disabled: set[str], overrides: set[str]) -> bool:
    """Checkable without a database, loads the default list once on first call."""
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
    """Both lists from the settings."""
    disabled = set(json.loads(db.get_setting("disabled_tools", "[]")))
    overrides = set(json.loads(db.get_setting("enabled_tools_override", "[]")))
    return disabled, overrides


def is_released_now(tool_key: str) -> bool:
    """The same question with the current state from the database."""
    disabled, overrides = read_release_state()
    return is_released(tool_key, disabled, overrides)
