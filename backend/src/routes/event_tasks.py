"""The task card of the services page, for accounts made from the event's access code."""
from fastapi import APIRouter, Depends, HTTPException

from src.dependencies import get_current_user
from src.features.event import tasks
from src.features.event.service import CLIENT_TASK_IDS
from src.i18n import get_locale, t

router = APIRouter(prefix="/event-tasks", tags=["event"])


@router.get("")
def read_tasks(current_user: dict = Depends(get_current_user)):
    return tasks.view_for(current_user["user_id"])


@router.post("/{task_id}")
def tick_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if task_id not in CLIENT_TASK_IDS:
        raise HTTPException(status_code=404, detail=t("event.taskNotFound", locale))
    user_id = current_user["user_id"]
    if tasks.card_for(user_id) is not None:
        tasks.add_done(user_id, task_id)
    return tasks.view_for(user_id)
