"""List, resolve and remove feedback entries."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from src.dependencies_rbac import require_permission
from src.features.feedback import repository as repo
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_USERS_FEEDBACK
from src.storage import USE_S3, stream_s3_object

router = APIRouter(tags=["admin: feedback"])

_require = require_permission(PERM_SET_USERS_FEEDBACK)


@router.get("/feedback")
def list_feedback(admin: dict = Depends(_require)):
    return {"feedback": repo.list_feedback()}


@router.get("/feedback/attachments/{attachment_id}")
def get_feedback_attachment(
    attachment_id: int,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    attachment = repo.get_attachment(attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail=t("feedback.notFound", locale))

    disposition = f'inline; filename="{attachment["filename"]}"'
    if USE_S3:
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


class SetFeedbackDoneRequest(BaseModel):
    done: bool


@router.patch("/feedback/{feedback_id}")
def set_feedback_done(
    feedback_id: int,
    payload: SetFeedbackDoneRequest,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    if not repo.set_feedback_done(feedback_id, payload.done):
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
