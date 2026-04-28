"""System prompt management: view, update, and reset."""

from fastapi import APIRouter, Depends, HTTPException

from src import database as db
from src.dependencies import get_admin_user

from src.routes.admin._models import UpdatePromptRequest
from src.routes.admin._registries import PROMPT_REGISTRY

router = APIRouter(tags=["admin"])


def _find_prompt(key: str) -> dict | None:
    return next((x for x in PROMPT_REGISTRY if x["key"] == key), None)


@router.get("/prompts")
async def get_prompts(_admin=Depends(get_admin_user)):
    result = []
    for p in PROMPT_REGISTRY:
        current = db.get_setting(p["key"], p["default"]) if p["editable"] else p["default"]
        result.append({
            "key": p["key"],
            "label": p["label"],
            "description": p["description"],
            "editable": p["editable"],
            "current_value": current,
            "default_value": p["default"],
        })
    return {"prompts": result}


@router.patch("/prompts/{key}")
async def update_prompt(key: str, body: UpdatePromptRequest, _admin=Depends(get_admin_user)):
    p = _find_prompt(key)
    if not p:
        raise HTTPException(status_code=404, detail="Prompt nicht gefunden")
    if not p["editable"]:
        raise HTTPException(status_code=400, detail="Dieser Prompt ist schreibgeschützt")
    if not body.value.strip():
        raise HTTPException(status_code=400, detail="Prompt darf nicht leer sein")
    db.set_setting(key, body.value)
    return {"ok": True}


@router.delete("/prompts/{key}/reset")
async def reset_prompt(key: str, _admin=Depends(get_admin_user)):
    p = _find_prompt(key)
    if not p or not p["editable"]:
        raise HTTPException(status_code=400, detail="Nicht erlaubt")
    db.set_setting(key, p["default"])
    return {"ok": True}
