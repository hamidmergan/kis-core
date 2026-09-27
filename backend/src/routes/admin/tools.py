"""Tool visibility: which tools are visible and active on the home page."""

import json

from fastapi import APIRouter, Depends, HTTPException

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t

from src.routes.admin._models import ToggleToolRequest
from src.routes.admin._registries import DEFAULT_DISABLED_TOOLS, TOOLS_CONFIG

from src.dependencies_rbac import require_permission
from src.permissions_registry import PERM_SET_TOOLS_RELEASE
from src.services.tool_release import is_released, read_release_state

router = APIRouter(tags=["admin: tools"])

# Release or block a tool.
_require = require_permission(PERM_SET_TOOLS_RELEASE)


@router.get("/tools")
def get_tools(_user=Depends(get_current_user)):
    """Return all tools with their enabled/disabled state. Accessible by all logged-in users."""
    disabled, overrides = read_release_state()
    return {
        "tools": [
            {**tool, "enabled": is_released(tool["key"], disabled, overrides)}
            for tool in TOOLS_CONFIG
        ]
    }


@router.patch("/tools/{tool_key}")
def toggle_tool(
    tool_key: str,
    body: ToggleToolRequest,
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    """Enable or disable a tool on the homepage. Admin only."""
    valid_keys = {tool["key"] for tool in TOOLS_CONFIG}
    if tool_key not in valid_keys:
        raise HTTPException(status_code=400, detail=t("admin.tools.unknownKey", locale))
    disabled, enabled_overrides = read_release_state()
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
