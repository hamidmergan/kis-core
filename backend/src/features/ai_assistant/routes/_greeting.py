"""The greeting only needs the topics, so it reads the summaries instead of the text."""

from src import database as db
from src.features.ai_assistant.summaries import summary_chunks


def greeting_chunks(source_ids: list[int] | None, sources_by_id: dict[int, dict]) -> list[dict]:
    """A summary per source, the first chunk where one is missing, nothing when no source has one."""
    if not source_ids:
        return []
    sources = [sources_by_id[sid] for sid in source_ids if sid in sources_by_id]
    summarized = {c["source_id"]: c for c in summary_chunks(sources)}
    if not summarized:
        return []
    out: list[dict] = []
    for sid in source_ids:
        if sid in summarized:
            out.append(summarized[sid])
            continue
        raw = db.get_aia_chunks_by_source(sid)
        if raw:
            out.append(raw[0])
    return out
