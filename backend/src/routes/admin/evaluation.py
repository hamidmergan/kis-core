"""Create and switch the one evaluation the platform currently offers."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.dependencies_rbac import require_permission
from src.features.evaluation import repository as repo
from src.features.evaluation.service import (
    MAX_INTRO_OUTRO_CHARS,
    MAX_LINK_LABEL_CHARS,
    MAX_LINK_URL_CHARS,
    MAX_TITLE_CHARS,
    summarize,
    validate_questions,
)
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_USERS_EVALUATION

router = APIRouter(prefix="/evaluation", tags=["admin: evaluation"])

_require = require_permission(PERM_SET_USERS_EVALUATION)


class QuestionPayload(BaseModel):
    id: str | None = None
    type: str
    text: str
    scale_low: str = ""
    scale_high: str = ""


class SaveConfigPayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_CHARS)
    intro_text: str = Field("", max_length=MAX_INTRO_OUTRO_CHARS)
    intro_link_label: str = Field("", max_length=MAX_LINK_LABEL_CHARS)
    intro_link_url: str = Field("", max_length=MAX_LINK_URL_CHARS)
    outro_text: str = Field("", max_length=MAX_INTRO_OUTRO_CHARS)
    outro_link_label: str = Field("", max_length=MAX_LINK_LABEL_CHARS)
    outro_link_url: str = Field("", max_length=MAX_LINK_URL_CHARS)
    questions: list[QuestionPayload]


class ActivePayload(BaseModel):
    active: bool


@router.get("")
def get_evaluation(admin: dict = Depends(_require)):
    return repo.get_config()


@router.put("")
def save_evaluation(
    payload: SaveConfigPayload,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    try:
        fragen = validate_questions([f.model_dump() for f in payload.questions])
    except ValueError:
        raise HTTPException(status_code=400, detail=t("evaluation.questionsInvalid", locale))
    config = {
        "title": payload.title.strip(),
        "intro_text": payload.intro_text.strip(),
        "intro_link_label": payload.intro_link_label.strip(),
        "intro_link_url": payload.intro_link_url.strip(),
        "outro_text": payload.outro_text.strip(),
        "outro_link_label": payload.outro_link_label.strip(),
        "outro_link_url": payload.outro_link_url.strip(),
        "questions": fragen,
    }
    repo.save_config(config)
    return {**config, "active": repo.get_config()["active"]}


@router.patch("/active")
def set_evaluation_active(payload: ActivePayload, admin: dict = Depends(_require)):
    repo.set_active(payload.active)
    return {"active": payload.active}


# Same period keys as the other statistics pages, plus "alle" because an
# evaluation hangs off one event rather than off a running year.
_ZEITRAEUME = {"30t": 30, "halbjahr": 182, "jahr": 365}


@router.get("/results")
def evaluation_results(
    admin: dict = Depends(_require),
    range: str = Query(default="alle", pattern="^(alle|jahr|halbjahr|30t)$"),
):
    tage = _ZEITRAEUME.get(range)
    seit = datetime.now() - timedelta(days=tage) if tage else None
    antworten = repo.list_responses(seit)
    return summarize(antworten, repo.get_config()["questions"])
