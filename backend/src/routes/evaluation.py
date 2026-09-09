"""The one active evaluation, as it looks to whoever is about to fill it out."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.dependencies import get_current_user
from src.dependencies_rbac import permissions_of
from src.features.access_codes import repository as access_repo
from src.features.evaluation import repository as repo
from src.features.evaluation.service import validate_answers
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_USERS_EVALUATION

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


def _may_see(user: dict) -> bool:
    """Visitors from a code with the switch, plus whoever runs the evaluation itself."""
    if permissions_of(user).has(PERM_SET_USERS_EVALUATION):
        return True
    return access_repo.shows_evaluation(user["user_id"])


class AnswerPayload(BaseModel):
    question_id: str
    value: str | int


class SubmitPayload(BaseModel):
    answers: list[AnswerPayload]


@router.get("/active")
def get_active_evaluation(user: dict = Depends(get_current_user)):
    config = repo.get_config()
    if not config["active"] or not _may_see(user):
        return {"active": False}
    return {**config, "already_responded": repo.has_responded(user["user_id"])}


@router.post("/submit")
def submit_evaluation(
    payload: SubmitPayload,
    user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    config = repo.get_config()
    if not config["active"] or not _may_see(user):
        raise HTTPException(status_code=404, detail=t("evaluation.notActive", locale))

    try:
        antworten = validate_answers([a.model_dump() for a in payload.answers], config["questions"])
    except ValueError:
        raise HTTPException(status_code=400, detail=t("evaluation.answersInvalid", locale))

    repo.create_response(user["user_id"], antworten)
    return {"status": "ok"}
