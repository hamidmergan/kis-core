"""Demo access: show the courses of the demo accounts and join them yourself."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t

from ._demo_tour_content import lege_rundgang_inhalte_an, lege_chat_beispiel_an

router = APIRouter(tags=["ai-assistant: demo"])


class DemoEnrollBody(BaseModel):
    workspace_uuid: str | None = None


class DemoLeaveBody(BaseModel):
    workspace_uuid: str


@router.get("/ai-assistant/demo/workspaces")
async def list_demo_workspaces(current_user: dict = Depends(get_current_user)):
    """All active courses of the demo accounts, without the internal ids."""
    return [
        {
            "uuid": row["uuid"],
            "title": row["title"],
            "description": row["description"],
            "source_count": row["source_count"],
            "joined": row["joined"],
            "via_demo": row["via_demo"],
            "owned": row["owned"],
        }
        for row in db.get_demo_workspaces(current_user["user_id"])
    ]


@router.post("/ai-assistant/demo/enroll")
async def enroll_in_demo(
    body: DemoEnrollBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Enrolls into a demo course, without an argument into all still open ones."""
    user_id = current_user["user_id"]
    kurse = db.get_demo_workspaces(user_id)
    if body.workspace_uuid:
        kurse = [k for k in kurse if k["uuid"] == body.workspace_uuid]
        if not kurse:
            raise HTTPException(status_code=404, detail=t("ai.demo.notFound", locale))
    joined = []
    for kurs in kurse:
        if kurs["joined"] or kurs["owned"]:
            continue
        if db.enroll_student(kurs["id"], user_id, None, via_demo=True):
            joined.append(kurs["uuid"])
    logger.info("Demo: Nutzer {} ist {} Kursen beigetreten", user_id, len(joined))
    return {"joined": joined}


@router.post("/ai-assistant/demo/leave")
async def leave_demo(
    body: DemoLeaveBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Withdraws the enrollment, everything else in the course stays."""
    user_id = current_user["user_id"]
    kurs = next((k for k in db.get_demo_workspaces(user_id) if k["uuid"] == body.workspace_uuid), None)
    if kurs is None:
        raise HTTPException(status_code=404, detail=t("ai.demo.notFound", locale))
    geloescht = db.delete_demo_enrollment(kurs["id"], user_id)
    logger.info("Demo: Nutzer {} hat Kurs {} verlassen: {}", user_id, kurs["uuid"], geloescht)
    return {"left": geloescht}


@router.post("/ai-assistant/demo/tour-content")
async def prepare_tour_content(
    body: DemoLeaveBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Puts the glossary entry and the note the guided tour shows in place."""
    user_id = current_user["user_id"]
    kurs = next((k for k in db.get_demo_workspaces(user_id) if k["uuid"] == body.workspace_uuid), None)
    if kurs is None:
        raise HTTPException(status_code=404, detail=t("ai.demo.notFound", locale))
    return lege_rundgang_inhalte_an(kurs["id"], user_id)


@router.post("/ai-assistant/demo/tour-chat-example")
async def prepare_tour_chat_example(
    body: DemoLeaveBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Puts the example question and answer in the chat, called only at that tour step."""
    user_id = current_user["user_id"]
    kurs = next((k for k in db.get_demo_workspaces(user_id) if k["uuid"] == body.workspace_uuid), None)
    if kurs is None:
        raise HTTPException(status_code=404, detail=t("ai.demo.notFound", locale))
    return {"added": lege_chat_beispiel_an(kurs["id"], user_id)}
