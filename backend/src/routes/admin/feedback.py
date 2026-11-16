"""List, resolve and remove feedback entries."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from src.dependencies_rbac import require_permission
from src.features.feedback import repository as repo
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_USERS_FEEDBACK
from src.storage import USE_S3, stream_s3_object
from src.utils import download_header

router = APIRouter(tags=["admin: feedback"])

_require = require_permission(PERM_SET_USERS_FEEDBACK)


@router.get("/feedback")
def list_feedback(admin: dict = Depends(_require)):
    return {"feedback": repo.list_feedback()}


@router.get("/feedback/open-count")
def count_open_feedback(admin: dict = Depends(_require)):
    return {"open": repo.count_open_feedback()}


@router.get("/feedback/attachments/{attachment_id}")
def get_feedback_attachment(
    attachment_id: int,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    attachment = repo.get_attachment(attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail=t("feedback.notFound", locale))

    if USE_S3:
        # The name is whatever the sender's file was called, bare it breaks the header outside Latin-1.
        disposition = download_header.attachment(attachment["filename"]).replace("attachment", "inline", 1)
        body_iter, content_length, _ = stream_s3_object(attachment["storage_key"])
        return StreamingResponse(
            body_iter,
            media_type=attachment["content_type"],
            headers={"Content-Disposition": disposition, "Content-Length": str(content_length)},
        )
    return FileResponse(
        path=attachment["storage_key"],
        media_type=attachment["content_type"],
        filename=attachment["filename"],
        content_disposition_type="inline",
    )


class SetFeedbackStatusRequest(BaseModel):
    status: Literal["open", "parked", "done"]


@router.patch("/feedback/{feedback_id}")
def set_feedback_status(
    feedback_id: int,
    payload: SetFeedbackStatusRequest,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    if not repo.set_feedback_status(feedback_id, payload.status):
        raise HTTPException(status_code=404, detail=t("feedback.notFound", locale))
    return {"status": "ok"}


@router.delete("/feedback/{feedback_id}")
def delete_feedback(
    feedback_id: int,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    if not repo.delete_feedback(feedback_id):
        raise HTTPException(status_code=404, detail=t("feedback.notFound", locale))
    return {"status": "ok"}
