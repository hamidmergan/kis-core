"""Status poll: progress while running, the result once finished."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t
from src.storage import load_result_json, load_result_meta


router = APIRouter()


@router.get("/{job_uuid}")
def get_job_status(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Poll job status. Returns progress while running, result when done."""
    job = db.get_job(job_uuid)
    # Not found and not yours both yield 404.
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))

    response: dict = {
        "job_uuid": job_uuid,
        "status": job["status"],
        "tool": job["tool"],
        "progress": None,
        "error": job["error_message"],
        "filename": job["result_filename"],
        "download_url": None,
        "result": None,
        "meta": None,
    }

    if job["progress"]:
        try:
            response["progress"] = json.loads(job["progress"])
        except Exception:
            pass

    if job["status"] in ("success", "awaiting_user") and job["result_path"]:
        result_path = Path(job["result_path"])

        if result_path.suffix == ".json":
            # Inline JSON result (e.g. screencast/translate)
            try:
                response["result"] = load_result_json(job["result_path"])
            except Exception as e:
                logger.error("Failed to load result JSON for {}: {}", job_uuid, e)
                raise HTTPException(status_code=500, detail=t("job.resultLoadFailed", locale))
        else:
            # Binary result (MP4, MP3) - provide download URL
            response["download_url"] = f"/jobs/{job_uuid}/download"

            # For render jobs: load subtitle + audio metadata
            meta = load_result_meta(job["user_id"], job_uuid)
            if meta is not None:
                response["meta"] = meta

    return response
