"""Corrects transcript lines that speech recognition got wrong, owner and tutors only."""

import asyncio
import re

from pydantic import BaseModel

from ._shared import (
    APIRouter,
    Depends,
    HTTPException,
    db,
    file_exists,
    get_current_user,
    get_file,
    get_locale,
    logger,
    t,
    _load_workspace_source,
    _require_workspace_manage,
)
from src.storage import aia_transcript_key, aia_vtt_key, put_bytes

router = APIRouter(tags=["ki-assistent: sources"])

_MAX_CUE_LEN = 1000
_MAX_CUES_PER_CALL = 200


class TranscriptCueEdit(BaseModel):
    index: int
    text: str


class EditTranscriptBody(BaseModel):
    lang: str
    cues: list[TranscriptCueEdit]


def _clean_cue_text(raw: str, locale: str) -> str:
    """One line without line breaks, a blank line inside would cut the cue in two."""
    text = re.sub(r"\s+", " ", raw or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail=t("ai.transcript.lineEmpty", locale))
    if len(text) > _MAX_CUE_LEN:
        raise HTTPException(
            status_code=400,
            detail=t("ai.transcript.lineTooLong", locale, max=_MAX_CUE_LEN),
        )
    return text


def _refresh_search_text(source: dict, segments: list[dict]) -> None:
    """Carries the correction into the searchable text the assistant quotes from."""
    from src.services.aia_chunker import segments_to_chunks
    from src.features.ai_assistant.tasks._helpers import _format_ts

    put_bytes(
        aia_transcript_key(source["file_path"]),
        "\n".join(
            f"[{_format_ts(s['start'])} - {_format_ts(s['end'])}] {s['text']}" for s in segments
        ).encode("utf-8"),
    )

    chunks = segments_to_chunks(segments)
    rows = db.get_aia_chunks_by_source(source["id"])
    if len(rows) != len(chunks):
        # The correction moved a chunk border, so the whole source is cut anew.
        db.delete_aia_chunks_by_source(source["id"])
        db.clear_pool_for_source(source["id"])
        changed = [
            (
                db.create_aia_chunk(
                    source_id=source["id"],
                    page_number=c["page_number"],
                    content=c["content"],
                    start_time=c.get("start_time"),
                    end_time=c.get("end_time"),
                ),
                c["content"],
            )
            for c in chunks
        ]
    else:
        changed = []
        for row, chunk in zip(rows, chunks):
            if row["content"] == chunk["content"]:
                continue
            db.update_aia_chunk_content(row["id"], chunk["content"])
            changed.append((row["id"], chunk["content"]))

    if not changed:
        return
    # A stale vector still finds the passage, so a failing provider must not lose the text.
    try:
        from src.services.aia_embeddings import get_embedding_provider_with_fallback

        provider = get_embedding_provider_with_fallback()
        vectors = provider.embed([content for _, content in changed])
        for (chunk_id, _), vector in zip(changed, vectors):
            db.update_chunk_embedding(chunk_id, vector)
    except Exception as e:
        logger.warning(
            "KI Tutor: transcript edit saved, re-embedding {} chunk(s) failed: {}", len(changed), e
        )


@router.patch("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/transcript")
async def edit_transcript(
    workspace_uuid: str,
    source_uuid: str,
    body: EditTranscriptBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Rewrites single transcript lines, timestamps and line count stay as they are."""
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    source = _load_workspace_source(source_uuid, workspace, locale)

    lang_clean = (body.lang or "").strip().lower()
    if not re.fullmatch(r"[a-z]{2,5}", lang_clean):
        raise HTTPException(status_code=400, detail=t("ai.transcript.invalidLangCode", locale))
    if not body.cues or len(body.cues) > _MAX_CUES_PER_CALL:
        raise HTTPException(status_code=400, detail=t("ai.transcript.lineOutOfRange", locale))

    vtt_key = aia_vtt_key(source["file_path"], lang_clean)
    if not await asyncio.to_thread(file_exists, vtt_key):
        raise HTTPException(status_code=404, detail=t("ai.transcript.notAvailable", locale))

    from src.services.subtitle_converter import segments_to_vtt, vtt_to_segments

    raw = await asyncio.to_thread(get_file, vtt_key)
    segments = vtt_to_segments(raw.decode("utf-8"))

    touched = 0
    for cue in body.cues:
        if cue.index < 0 or cue.index >= len(segments):
            raise HTTPException(status_code=409, detail=t("ai.transcript.lineOutOfRange", locale))
        text = _clean_cue_text(cue.text, locale)
        if segments[cue.index]["text"] == text:
            continue
        segments[cue.index]["text"] = text
        touched += 1

    if touched == 0:
        return {"changed": 0}

    await asyncio.to_thread(put_bytes, vtt_key, segments_to_vtt(segments).encode("utf-8"))

    # Only the track the index was built from feeds the assistant, a translation does not.
    if lang_clean == (source.get("language") or "").strip().lower():
        await asyncio.to_thread(_refresh_search_text, source, segments)

    logger.info(
        "KI Tutor: transcript {} of source {} corrected, {} line(s)", lang_clean, source_uuid, touched
    )
    return {"changed": touched}
