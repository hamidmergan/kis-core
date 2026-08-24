"""Was Schritt 6 beim Betreten braucht und was er beim Aendern speichert."""

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.dependencies import get_current_user
from src.features.jobs.repository import get_job
from src.i18n import get_locale, t
from src.storage import get_audio_slide_count, get_job_file, hat_audio_slide, save_job_file

router = APIRouter(tags=["screencast: einstellungen"])


class EinstellungenRequest(BaseModel):
    """Alles, was Schritt 6 zeigt, in einem Rutsch."""

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
    """Gleiche Antwort fuer fehlend und fremd, sonst liesse sich raten."""
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
    """Gespeicherte Einstellungen, Abzug des letzten Laufs und wer schon Ton hat."""
    user_id = _auftrag(job_uuid, current_user, locale)
    stand = _lies_json(user_id, job_uuid, "vertonter_stand.json")
    scripts = _lies_json(user_id, job_uuid, "render_scripts.json") or []
    anzahl = max(len(scripts), get_audio_slide_count(user_id, job_uuid))
    return {
        "einstellungen": _lies_json(user_id, job_uuid, "einstellungen.json"),
        "stand": stand,
        "hat_ton": [hat_audio_slide(user_id, job_uuid, i) for i in range(anzahl)],
    }


@router.put("/screencast/{job_uuid}/einstellungen")
def einstellungen_speichern(
    job_uuid: str,
    body: EinstellungenRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Gespeichert wird beim Aendern, damit morgen nichts auf Standard steht."""
    user_id = _auftrag(job_uuid, current_user, locale)
    save_job_file(user_id, job_uuid, "einstellungen.json",
                  json.dumps(body.model_dump(), ensure_ascii=False).encode())
    return {"status": "gespeichert"}
