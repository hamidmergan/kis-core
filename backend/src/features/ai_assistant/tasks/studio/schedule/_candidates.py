"""The chunks of a source in reading order and the timestamp of a spot in them."""

from loguru import logger

from src import database as db
from src.features.ai_assistant.routes._media_files import _load_transcript_segments
from src.services.aia_transcript_offsets import TranscriptIndex


def _load_source_chunks(source_id: int) -> list[dict]:
    """Return ordered chunks with their positions (page or timestamp)."""
    chunks = db.get_aia_chunks_by_source(source_id)
    if not chunks:
        return []
    return sorted(
        chunks,
        key=lambda c: (c.get("start_time") or 0, c.get("page_number") or 0, c.get("id", 0)),
    )


def _transcript_index(src: dict, chunks: list[dict]) -> TranscriptIndex | None:
    """The source's timeline, loaded once per source, media only."""
    if not any(c.get("start_time") is not None for c in chunks):
        return None
    segmente = _load_transcript_segments(src)
    if not segmente:
        logger.info("Terminsuche: kein Transkript zu Quelle {}, Zeitmarken bleiben am "
                    "Chunk-Anfang", src.get("id"))
        return None
    return TranscriptIndex(segmente)


def _fundstelle_zeit(index: TranscriptIndex | None, chunk: dict,
                     offset: int) -> float | None:
    """Timestamp for a spot in the chunk text, otherwise the chunk start."""
    st = chunk.get("start_time")
    if st is None or index is None:
        return st
    genau = index.start_at(chunk, offset)
    return genau if genau is not None else st
