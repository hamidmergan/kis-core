"""Tool-Visibility: welche Tools sind auf der Homepage sichtbar/aktiv."""

import json

from fastapi import APIRouter, Depends, HTTPException

from src import database as db
from src.dependencies import get_admin_user, get_current_user
from src.i18n import get_locale, t

from src.routes.admin._models import ToggleToolRequest
from src.routes.admin._registries import DEFAULT_DISABLED_TOOLS, TOOLS_CONFIG

router = APIRouter(tags=["admin: tools"])


@router.get("/tools")
def get_tools(_user=Depends(get_current_user)):
    """Return all tools with their enabled/disabled state. Accessible by all logged-in users."""
    disabled = set(json.loads(db.get_setting("disabled_tools", "[]")))
    enabled_overrides = set(json.loads(db.get_setting("enabled_tools_override", "[]")))

    def _is_enabled(key: str) -> bool:
        if key in disabled:
            return False
        if key in DEFAULT_DISABLED_TOOLS and key not in enabled_overrides:
            return False
        return True

    return {
        "tools": [
            {**tool, "enabled": _is_enabled(tool["key"])}
            for tool in TOOLS_CONFIG
        ]
    }


@router.patch("/tools/{tool_key}")
def toggle_tool(
    tool_key: str,
    body: ToggleToolRequest,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    """Enable or disable a tool on the homepage. Admin only."""
    valid_keys = {tool["key"] for tool in TOOLS_CONFIG}
    if tool_key not in valid_keys:
        raise HTTPException(status_code=400, detail=t("admin.tools.unknownKey", locale))
    disabled = set(json.loads(db.get_setting("disabled_tools", "[]")))
    enabled_overrides = set(json.loads(db.get_setting("enabled_tools_override", "[]")))
    if body.enabled:
        disabled.discard(tool_key)
        if tool_key in DEFAULT_DISABLED_TOOLS:
            enabled_overrides.add(tool_key)
    else:
        enabled_overrides.discard(tool_key)
        if tool_key not in DEFAULT_DISABLED_TOOLS:
            disabled.add(tool_key)
    db.set_setting("disabled_tools", json.dumps(list(disabled)))
    db.set_setting("enabled_tools_override", json.dumps(list(enabled_overrides)))
    return {"ok": True}
