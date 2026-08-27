"""What step 6 needs on entry and what it saves on change."""

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.dependencies import get_current_user
from src.features.jobs.repository import get_job
from src.i18n import get_locale, t
from src.storage import audio_folien_mit_ton, get_audio_slide_count, get_job_file, save_job_file

router = APIRouter(tags=["screencast: einstellungen"])


class EinstellungenRequest(BaseModel):
    """Everything step 6 shows, in one go."""

    provider_id: int = 0
    voice_id: str = ""
    voice_label: str = ""
    target_lang: str = ""
    speed: float = 0.9
    slide_pause: float = 1.0
    dpi: int = 96
    subtitles: bool = False
    video_folien: list[int] | None = None
    neu_vertonen: list[int] = []


def _auftrag(job_uuid: str, current_user: dict, locale: str) -> int:
    """The same answer for missing and foreign, otherwise it could be guessed."""
    if not re.match(r"^[a-f0-9]{32}$", job_uuid):
        raise HTTPException(status_code=400, detail=t("job.invalidUuid", locale))
    job = get_job(job_uuid)
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    return job["user_id"]


def _lies_json(user_id: int, job_uuid: str, name: str):
    try:
        return json.loads(get_job_file(user_id, job_uuid, name))
    except Exception:
        return None


@router.get("/screencast/{job_uuid}/vertonungs-stand")
def vertonungs_stand(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Saved settings, the deduction of the last run and who already has audio."""
    user_id = _auftrag(job_uuid, current_user, locale)
    stand = _lies_json(user_id, job_uuid, "vertonter_stand.json")
    scripts = _lies_json(user_id, job_uuid, "render_scripts.json") or []
    # The number space comes from the slides, audio/ can hold old audio of excluded ones.
    anzahl = len(scripts) or get_audio_slide_count(user_id, job_uuid)
    mit_ton = audio_folien_mit_ton(user_id, job_uuid)
    return {
        "einstellungen": _lies_json(user_id, job_uuid, "einstellungen.json"),
        "stand": stand,
        "hat_ton": [i in mit_ton for i in range(anzahl)],
    }


@router.put("/screencast/{job_uuid}/einstellungen")
def einstellungen_speichern(
    job_uuid: str,
    body: EinstellungenRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Saved on change so nothing sits on the default tomorrow."""
    user_id = _auftrag(job_uuid, current_user, locale)
    save_job_file(user_id, job_uuid, "einstellungen.json",
                  json.dumps(body.model_dump(), ensure_ascii=False).encode())
    return {"status": "gespeichert"}
