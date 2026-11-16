"""What several route files need: the caller's own job, their id, the session cookie, the upload size check."""

import re

from fastapi import HTTPException, Request, Response

from src import database as db
from src.dependencies import get_settings
from src.i18n import t
from src.services import tool_limits

JOB_UUID = re.compile(r"^[a-f0-9]{32}$")

SESSION_MAX_AGE = 86400

MIN_PASSWORD_LENGTH = 8


def own_job(job_uuid: str, current_user: dict, locale: str, tool: str | None = None,
            not_found: str = "job.notFound") -> dict:
    """The caller's job, missing and foreign answer alike so a uuid cannot be probed."""
    if not JOB_UUID.match(job_uuid):
        raise HTTPException(status_code=400, detail=t("job.invalidUuid", locale))
    job = db.get_job(job_uuid)
    if (not job or job["user_id"] != current_user.get("user_id", 0)
            or (tool is not None and job["tool"] != tool)):
        raise HTTPException(status_code=404, detail=t(not_found, locale))
    return job


def require_user_id(user: dict, locale: str) -> int:
    """The id of the signed-in account, 401 for a session without one."""
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail=t("auth.notAuthenticated", locale))
    return user_id


def set_session_cookie(response: Response, token: str) -> None:
    """The one shape of the session cookie, every way in sets it alike."""
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        secure=get_settings().production,
    )


def enforce_upload_size(request: Request, locale: str) -> None:
    """Refuses a request whose announced size is above the admin's upload limit."""
    announced = request.headers.get("content-length")
    limit = tool_limits.max_upload_bytes()
    if announced is not None and int(announced) > limit:
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb", locale, max=limit // (1024 * 1024)))
