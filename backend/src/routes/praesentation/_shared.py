"""What every presentation route needs: the own job, the busy check, one model call."""

import json

from fastapi import HTTPException
from pydantic import BaseModel

from src.i18n import t
from src.routes import _shared

LAEUFT = ("running", "pending", "queued", "waiting_retry")


class ChatTurn(BaseModel):
    role: str
    content: str


class RegenRequest(BaseModel):
    messages: list[ChatTurn] = []
    selected_text: str = ""


def own_job(job_uuid: str, current_user: dict, locale: str) -> dict:
    """The presentation job of this person."""
    return _shared.own_job(job_uuid, current_user, locale, tool="praesentation")


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
