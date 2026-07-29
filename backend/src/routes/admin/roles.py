"""Admin endpoints for managing custom roles and assigning roles to users."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src import database as db
from src.dependencies import get_admin_user
from src.tools_registry import ALL_TOOL_KEYS

router = APIRouter(tags=["admin: roles"])

AIA_ACCESS_LEVELS: tuple[str, ...] = ("none", "read", "edit")


class RolePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    aia_access: Literal["none", "read", "edit"] = "none"
    allowed_tools: list[str] = Field(default_factory=list)


def _validate_tools(tool_keys: list[str]) -> list[str]:
    bad = [k for k in tool_keys if k not in ALL_TOOL_KEYS]
    if bad:
        raise HTTPException(status_code=400, detail=f"Unknown tool keys: {bad}")
    seen: set[str] = set()
    out: list[str] = []
    for k in tool_keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


@router.get("/roles")
def list_roles(_admin=Depends(get_admin_user)):
    return {
        "system_roles": ["admin", "staff", "user"],
        "aia_access_levels": list(AIA_ACCESS_LEVELS),
        "custom_roles": db.list_custom_roles(),
        "available_tools": list(ALL_TOOL_KEYS),
    }


@router.post("/roles")
def create_role(payload: RolePayload, _admin=Depends(get_admin_user)):
    tools = _validate_tools(payload.allowed_tools)
    new_id = db.create_custom_role(payload.name.strip(), payload.aia_access, tools)
    return db.get_custom_role(new_id)


@router.put("/roles/{role_id}")
def update_role(role_id: int, payload: RolePayload, _admin=Depends(get_admin_user)):
    if db.get_custom_role(role_id) is None:
        raise HTTPException(status_code=404, detail="Role not found")
    tools = _validate_tools(payload.allowed_tools)
    db.update_custom_role(role_id, payload.name.strip(), payload.aia_access, tools)
    return db.get_custom_role(role_id)


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, _admin=Depends(get_admin_user)):
    if db.get_custom_role(role_id) is None:
        raise HTTPException(status_code=404, detail="Role not found")
    db.delete_custom_role(role_id)
    return {"status": "ok"}
