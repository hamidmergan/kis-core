"""Numbers the sources of an answer and builds the spot list the browser shows."""

import re
from pathlib import Path

from ._media_files import _MEDIA_EXTENSIONS, _load_transcript_segments


def build_source_qmap(all_sources_list: dict, chunks: list[dict],
                      search_source_ids) -> tuple[dict, list]:
    """Gives every source of the selection its number Q1, Q2, ... for the chips."""
    source_id_to_qnum: dict[int, int] = {}
    source_qmap: list[dict] = []  # [{qnum, uuid, filename}, ...]
    # The whole selection is numbered, not only the sources with a hit.
    chunk_sids = {c["source_id"] for c in chunks}
    qmap_sids = set(search_source_ids or []) | chunk_sids
    qnum_counter = 0
    for sid in all_sources_list:
        if sid not in qmap_sids:
            continue
        qnum_counter += 1
        source_id_to_qnum[sid] = qnum_counter
        src = all_sources_list[sid]
        source_qmap.append({
            "qnum": qnum_counter,
            "uuid": src["uuid"],
            "filename": src["filename"],
            "is_media": Path(src["filename"]).suffix.lower() in _MEDIA_EXTENSIONS,
        })
    # An unexpected source gets a number too, otherwise its citation is lost.
    for chunk in chunks:
        sid = chunk["source_id"]
        if sid not in source_id_to_qnum:
            qnum_counter += 1
            source_id_to_qnum[sid] = qnum_counter
    return source_id_to_qnum, source_qmap


def load_transcripts(chunks: list[dict], all_sources_list: dict) -> dict:
    """Preloads the Whisper segments of every media source that has a hit."""
    # Preload Whisper segments so timestamps make it into the media chunks.
    transcript_by_source: dict[int, list[dict]] = {}
    for chunk in chunks:
        sid = chunk["source_id"]
        if chunk.get("start_time") is not None and sid not in transcript_by_source:
            src = all_sources_list.get(sid)
            if src:
                transcript_by_source[sid] = _load_transcript_segments(src)
    return transcript_by_source


def build_source_pages(chunks: list[dict], all_sources_list: dict, *,
                       umformen: bool, umform_pages: list[dict],
                       popup_entry) -> list[dict]:
    """The spots under the answer: the reshaped ones, the selection, or the hits."""
    source_pages: list[dict] = []
    if umformen:
        # The same spots as in the round being reshaped.
        return list(umform_pages)
    if popup_entry:
        return [popup_entry]
    for chunk in chunks:
        # A summary has neither a page nor a time, so there is no spot to jump to.
        if chunk.get("page_number") is None and chunk.get("start_time") is None:
            continue
        source = all_sources_list.get(chunk["source_id"])
        if source:
            raw = (chunk.get("content") or "").strip()
            raw = re.sub(r"^\d{1,3}\s+", "", raw).strip()
            # Skip leading partial word (chunk overlap can start mid-word)
            first_space = raw.find(" ")
            if first_space > 0 and first_space < 20:
                raw = raw[first_space + 1:]
            snippet = raw[:400].strip()
            entry = {
                "source_uuid": source["uuid"],
                "filename": source["filename"],
                "page_number": chunk["page_number"],
                "source_text": snippet,
            }
            if chunk.get("start_time") is not None:
                entry["start_time"] = chunk["start_time"]
                entry["end_time"] = chunk.get("end_time")
            source_pages.append(entry)
    source_pages.sort(key=lambda x: x["page_number"])
    return source_pages
