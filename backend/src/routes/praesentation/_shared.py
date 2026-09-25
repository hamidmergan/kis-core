"""What every presentation route needs: the own job, the busy check, one model call."""

import json
import re

from fastapi import HTTPException
from pydantic import BaseModel

from src import database as db
from src.i18n import t

_UUID = re.compile(r"^[a-f0-9]{32}$")
LAEUFT = ("running", "pending", "queued", "waiting_retry")


class ChatTurn(BaseModel):
    role: str
    content: str


class RegenRequest(BaseModel):
    messages: list[ChatTurn] = []
    selected_text: str = ""


def own_job(job_uuid: str, current_user: dict, locale: str) -> dict:
    """Missing and foreign answer alike, otherwise a uuid could be guessed."""
    if not _UUID.match(job_uuid):
        raise HTTPException(status_code=400, detail=t("job.invalidUuid", locale))
    job = db.get_job(job_uuid)
    if not job or job["tool"] != "praesentation" or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    return job


def nicht_beschaeftigt(job: dict, locale: str) -> None:
    if job["status"] in LAEUFT:
        raise HTTPException(status_code=409, detail=t("praesentation.running", locale))


def progress_final(job: dict) -> bool:
    """Whether the job's last recorded stage was working toward a finalize, so a resume keeps the same intent."""
    roh = job.get("progress")
    if isinstance(roh, dict):
        return bool(roh.get("final"))
    try:
        daten = json.loads(roh) if roh else {}
    except (TypeError, ValueError):
        return False
    return bool(daten.get("final")) if isinstance(daten, dict) else False


def llm_antwort(nachrichten: list[dict], provider_id: int | None = None) -> str:
    """One synchronous model call, on the provider the run was started with."""
    from src.services import feature_router
    from src.services.feature_provider_choices import binding_for
    from src.services.json_llm import call_json_llm

    llm = feature_router.make_llm_client(binding_for("chat", provider_id))
    return call_json_llm(llm, nachrichten, endpoint="praesentation").choices[0].message.content or ""


def verlauf(body: RegenRequest) -> list[dict]:
    return [{"role": turn.role, "content": turn.content} for turn in body.messages]
