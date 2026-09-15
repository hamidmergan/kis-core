"""Saying one contribution differently without touching the rest."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from src.dependencies import get_current_user
from src.features.podcast import script as skript
from src.features.podcast import store
from src.i18n import get_locale, t
from src.routes.podcast._shared import own_job

router = APIRouter(tags=["podcast"])

# How much of the conversation the model sees around the contribution.
_UMFELD = 2


def _name(params, line) -> str:
    """The speaking person, or their number when the cast no longer holds them."""
    if 0 <= line.speaker < len(params.persons):
        return params.persons[line.speaker].name
    return f"Person {line.speaker + 1}"


class ChatTurn(BaseModel):
    role: str
    content: str


class RephraseRequest(BaseModel):
    line_id: str
    # Empty when the old one-click rewrite asks, filled when the chat window asks.
    messages: list[ChatTurn] = []
    selected_text: str = ""


@router.post("/podcast/{job_uuid}/rephrase")
async def rephrase_line(
    job_uuid: str,
    body: RephraseRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Returns the new text, saving stays the caller's job."""
    job = own_job(job_uuid, current_user, locale)
    if job["status"] in ("running", "pending", "queued", "waiting_retry"):
        raise HTTPException(status_code=409, detail=t("podcast.running", locale))
    user_id = job["user_id"]
    zeilen = store.load_lines(user_id, job_uuid)
    params = store.load_params(user_id, job_uuid)
    stelle = next((i for i, l in enumerate(zeilen) if l.id == body.line_id), -1)
    if stelle < 0 or not params:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    if params.self_written:
        raise HTTPException(status_code=409, detail=t("podcast.selfWrittenNoAi", locale))

    umfeld = [l.text for l in zeilen[max(0, stelle - _UMFELD) : stelle + _UMFELD + 1] if l.id != body.line_id]
    verlauf = [{"role": t.role, "content": t.content} for t in body.messages]
    if verlauf:
        wunsch = next((t["content"] for t in reversed(verlauf) if t["role"] == "user"), "")
        quelle = skript.source_excerpt(
            store.load_source(user_id, job_uuid),
            [zeilen[stelle].text, body.selected_text, wunsch],
            skript.REFINE_SOURCE_CHARS,
        )
        # With names, so the model does not answer in the voice of the neighbour.
        benannt = [f"{_name(params, l)}: {l.text}"
                   for l in zeilen[max(0, stelle - _UMFELD) : stelle + _UMFELD + 1]
                   if l.id != body.line_id]
        nachrichten = skript.refine_messages(zeilen[stelle], params, benannt, quelle, verlauf,
                                             body.selected_text.strip(),
                                             position=(stelle + 1, len(zeilen)))
    else:
        nachrichten = skript.rephrase_messages(zeilen[stelle], params, umfeld)
    try:
        from src.services import feature_router
        from src.services.aia_json_llm import call_json_llm

        binding = feature_router.resolve("chat")
        llm = feature_router.make_llm_client(binding)
        antwort = call_json_llm(llm, nachrichten)
        neu = skript.clean_rephrased(antwort.choices[0].message.content or "", zeilen[stelle].text)
    except Exception as e:  # noqa: BLE001 — der Anbieter ist die einzige Fehlerquelle hier
        logger.warning("Podcast: Umformulieren gescheitert: {}", e)
        raise HTTPException(status_code=502, detail=t("podcast.rephraseFailed", locale)) from e
    return {"line_id": body.line_id, "text": neu}
