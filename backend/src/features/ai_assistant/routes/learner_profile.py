"""Student-facing learner-profile routes. Global per user, so no workspace in the
path. The student sees the profile, deletes single entries or all, toggles tracking
and exports. This is the transparency and control the data-protection choice needs."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from src import database as db
from src.dependencies import get_current_user

router = APIRouter(tags=["ki-assistent: learner-profile"])


class EnabledBody(BaseModel):
    enabled: bool


def build_profile_markdown(level, weaknesses) -> str:
    """A readable Markdown export of one learner profile. Pure, so it is unit tested."""
    lines = ["# Mein Lernprofil", ""]
    lines.append(f"Sprachniveau: {level}" if level else "Sprachniveau: kein Level gesetzt")
    lines.append("")
    lines.append("## Offene Schwächen")
    if not weaknesses:
        lines.append("Aktuell keine offenen Schwächen.")
    else:
        for w in weaknesses:
            lines.append(
                f"- {w['label']} ({w['category']}), Gewicht {w['effective_weight']}, "
                f"{w['hit_count']} mal aufgetreten"
            )
    return "\n".join(lines)


@router.get("/ai-assistant/learner-profile")
async def get_learner_profile(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    ll = db.get_user_language_level(user_id)
    return {
        "enabled": db.is_learning_profile_enabled(user_id),
        "level": ll["language_level"],
        "level_set_at": ll["language_level_set_at"].isoformat() if ll["language_level_set_at"] else None,
        "weaknesses": db.get_learner_weaknesses(user_id),
    }


@router.delete("/ai-assistant/learner-profile/weaknesses/{weakness_id}")
async def delete_one(weakness_id: int, current_user: dict = Depends(get_current_user)):
    ok = db.delete_learner_weakness(weakness_id, current_user["user_id"])
    return {"deleted": ok}


@router.delete("/ai-assistant/learner-profile/weaknesses")
async def delete_all(current_user: dict = Depends(get_current_user)):
    return {"deleted": db.delete_all_learner_weaknesses(current_user["user_id"])}


@router.put("/ai-assistant/learner-profile/enabled")
async def set_enabled(body: EnabledBody, current_user: dict = Depends(get_current_user)):
    db.set_learning_profile_enabled(current_user["user_id"], body.enabled)
    return {"enabled": body.enabled}


@router.get("/ai-assistant/learner-profile/export")
async def export_profile(fmt: str = "json", current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    ll = db.get_user_language_level(user_id)
    weaknesses = db.get_learner_weaknesses(user_id)
    if fmt == "md":
        return PlainTextResponse(
            build_profile_markdown(ll["language_level"], weaknesses),
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=lernprofil.md"},
        )
    return {
        "level": ll["language_level"],
        "weaknesses": weaknesses,
    }


@router.get("/ai-assistant/workspaces/{workspace_uuid}/learner-profiles/export")
async def export_enrolled_profiles(
    workspace_uuid: str, current_user: dict = Depends(get_current_user),
):
    """Owner exports the profiles of students enrolled in this workspace. Access is
    gated by ownership, the profile content itself stays global per user."""
    ws = db.get_aia_workspace(workspace_uuid)
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")
    if ws["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="owner only")
    profiles = []
    for uid in db.get_enrolled_user_ids(ws["id"]):
        ll = db.get_user_language_level(uid)
        profiles.append({
            "user_id": uid,
            "level": ll["language_level"],
            "weaknesses": db.get_learner_weaknesses(uid),
        })
    return {"workspace_uuid": workspace_uuid, "profiles": profiles}
