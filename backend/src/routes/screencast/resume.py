"""Resume endpoints: reconstruct the wizard step + existence check for job folder."""

import json
import re

from fastapi import APIRouter, Depends, HTTPException

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t
from src.storage import get_job_file, load_result_json

router = APIRouter(tags=["screencast: resume"])

# Order defines the step detection on resume
_SCRIPT_FILES = (
    ("accepted_scripts.json", "tts-settings"),
    ("user_scripts.json", "script-review"),
    ("suggested_scripts.json", "script-review"),
)


def _load_scripts_from_job(user_id: int, translate_job_uuid: str) -> tuple[list[str], str | None]:
    """Return (scripts, step) from the first existing script file."""
    for filename, resolved_step in _SCRIPT_FILES:
        try:
            scripts = json.loads(get_job_file(user_id, translate_job_uuid, filename))
            return scripts, resolved_step
        except Exception:
            continue
    return [], None


def _load_slide_images(result_path: str | None) -> list[str]:
    if not result_path:
        return []
    try:
        result_data = load_result_json(result_path)
        return result_data.get("slide_images", [])
    except Exception:
        return []


@router.get("/screencast/resume/{translate_job_uuid}")
async def get_resume_data(
    translate_job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Reconstruct workflow state from job folder for resuming an awaiting_user screencast job."""
    if not re.match(r"^[a-f0-9]{32}$", translate_job_uuid):
        raise HTTPException(status_code=400, detail=t("job.invalidUuid", locale))
    job = db.get_job(translate_job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    if job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=403, detail=t("job.accessDenied", locale))
    # awaiting_user → normal wizard resume.
    # failed → screencast render failed; let the user re-open the wizard at the
    # last input step (tts-settings if accepted_scripts.json exists) so they can
    # tweak settings before re-rendering instead of immediately re-queuing.
    if job["status"] not in ("awaiting_user", "failed"):
        raise HTTPException(status_code=409, detail=t("job.notInputState", locale))

    tool = job["tool"]
    user_id = job["user_id"]
    slide_texts: list[str] = []

    try:
        user_prompt = get_job_file(user_id, translate_job_uuid, "prompt.txt").decode()
    except Exception:
        user_prompt = ""

    if tool == "screencast_translate":
        try:
            slide_texts = json.loads(get_job_file(user_id, translate_job_uuid, "scripts.txt"))
        except Exception:
            raise HTTPException(status_code=404, detail=t("job.dataUnavailable", locale))
    elif tool == "screencast_demo_render":
        try:
            slide_texts = json.loads(get_job_file(user_id, translate_job_uuid, "scripts.txt"))
        except Exception:
            pass

    slide_images = _load_slide_images(job.get("result_path"))
    scripts, resolved_step = _load_scripts_from_job(user_id, translate_job_uuid)

    if scripts:
        step = resolved_step
    else:
        step = "user-prompt" if user_prompt else "translation-review"

    return {
        "tool": tool,
        "step": step,
        "slide_texts": slide_texts,
        "scripts": scripts,
        "slide_images": slide_images,
        "original_filename": job["original_filename"] or "",
        "user_prompt": user_prompt,
    }


@router.get("/screencast/folder-exists/{translate_job_uuid}")
async def check_folder_exists(
    translate_job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Check if the job folder (scripts.txt) still exists in storage. Lightweight pre-flight check."""
    if not re.match(r"^[a-f0-9]{32}$", translate_job_uuid):
        raise HTTPException(status_code=400, detail=t("job.invalidUuid", locale))
    job = db.get_job(translate_job_uuid)
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    try:
        get_job_file(job["user_id"], translate_job_uuid, "scripts.txt")
        return {"exists": True}
    except Exception:
        return {"exists": False}
