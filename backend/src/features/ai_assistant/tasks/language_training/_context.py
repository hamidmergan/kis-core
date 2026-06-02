"""Context builder for mode='source': pulls chunks/summaries from N sources
and packs them into a budget-limited context string for the LLM prompt."""

from dataclasses import dataclass, field

from src import database as db

from src.features.ai_assistant.tasks.language_training._text_utils import (
    normalize_for_segment_lookup,
)


@dataclass
class QuelleContext:
    """Collected metadata for mode='source' generation."""
    context: str  # finished LLM context (trimmed)
    first_label: str
    multi_label: str
    source_hint: str  # "folgender Source" / "folgenden Sources"
    time_map: dict[tuple[str, int], float] = field(default_factory=dict)
    source_by_name: dict[str, dict] = field(default_factory=dict)
    segments_by_label: dict[str, list[dict]] = field(default_factory=dict)


def build_source_context(uuids: list[str], tool: str) -> QuelleContext | None:
    """Build context string + meta maps from N sources. None = no content available."""
    context_parts: list[str] = []
    first_label = ""
    time_map: dict[tuple[str, int], float] = {}
    source_by_name: dict[str, dict] = {}
    segments_by_label: dict[str, list[dict]] = {}

    # karteikarten needs the full set of raw chunks (LLM quotes verbatim for
    # evidence validation); all other tools use a capped slice of chunks.
    use_chunks = tool == "karteikarten"

    for suuid in uuids:
        source = db.get_aia_source(suuid)
        if not source:
            continue
        source_label = source["filename"]
        source_by_name[source_label] = source
        if not first_label:
            first_label = source_label

        chunks_all = db.get_chunks_by_source(source["id"]) if use_chunks else None

        if use_chunks and chunks_all:
            for c in chunks_all:
                if c.get("start_time") is not None:
                    time_map[(source_label, c["page_number"])] = c["start_time"]
            # Load Whisper segments for sub-chunk timestamp resolution on media sources
            if any(c.get("start_time") is not None for c in chunks_all):
                from src.features.ai_assistant.routes._helpers import _load_transcript_segments
                segments_by_label[source_label] = _load_transcript_segments(source)
            parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks_all]
            context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))
        else:
            chunks = db.get_chunks_by_source(source["id"])
            if chunks:
                for c in chunks:
                    if c.get("start_time") is not None:
                        time_map[(source_label, c["page_number"])] = c["start_time"]
                parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks[:30]]
                context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))

    if not context_parts:
        return None

    # Fair budget split: 200k chars total, whole lines
    budget_per_source = 200000 // len(context_parts)
    trimmed: list[str] = []
    for part in context_parts:
        lines = part.split("\n")
        header = lines[0]
        kept = [header]
        size = len(header)
        for line in lines[1:]:
            if size + len(line) + 1 > budget_per_source:
                break
            kept.append(line)
            size += len(line) + 1
        trimmed.append("\n".join(kept))

    multi_label = first_label if len(uuids) == 1 else f"{len(uuids)} Sources"
    source_hint = "folgender Source" if len(uuids) == 1 else "folgenden Sources"

    return QuelleContext(
        context="\n\n".join(trimmed),
        first_label=first_label,
        multi_label=multi_label,
        source_hint=source_hint,
        time_map=time_map,
        source_by_name=source_by_name,
        segments_by_label=segments_by_label,
    )


def resolve_segment_start(
    segments_by_label: dict[str, list[dict]],
    source_label: str,
    evidence: str,
    fallback: float | None,
) -> float | None:
    """For media sources: find the Whisper segment that contains the evidence, and
    return its start_time. Fall back to the chunk start_time on no match.

    Without this resolution, a ~1000-char chunk covering 60-120s would give all
    citations the same start time instead of the moment of the quote.
    """
    segments = segments_by_label.get(source_label) or []
    if not segments or not evidence:
        return fallback

    ev = normalize_for_segment_lookup(evidence)
    if not ev:
        return fallback

    # Sliding window: find segment whose normalized text overlaps maximally with the
    # start of the evidence (the first words tell where the quote begins)
    ev_words = ev.split()
    probe = " ".join(ev_words[: min(12, len(ev_words))])
    if len(probe) < 8:
        return fallback
    best: tuple[int, float] | None = None  # (shared_chars, seg_start)
    for i, seg in enumerate(segments):
        seg_norm = normalize_for_segment_lookup(seg["text"])
        if not seg_norm:
            continue
        if probe in seg_norm:
            return seg["start"]
        # Evidence may span a segment boundary: suffix match + neighbor prefix
        overlap = 0
        for k in range(min(len(seg_norm), len(probe)), 6, -1):
            if seg_norm.endswith(probe[:k]):
                overlap = k
                break
        if overlap and i + 1 < len(segments):
            nxt = normalize_for_segment_lookup(segments[i + 1]["text"])
            if nxt.startswith(probe[overlap:overlap + 40]):
                return seg["start"]
        if overlap and (best is None or overlap > best[0]):
            best = (overlap, seg["start"])
    return best[1] if best else fallback


def find_all_pages(
    source_by_name: dict[str, dict],
    time_map: dict[tuple[str, int], float],
    segments_by_label: dict[str, list[dict]],
    search_term: str,
) -> list[dict]:
    """Find all pages (across all sources) where search_term appears in the chunk text."""
    from src.features.ai_assistant.tasks.language_training._text_utils import normalize_chunk

    term_lower = search_term.lower()
    if not term_lower:
        return []
    seen: set[tuple[str, int]] = set()
    result: list[dict] = []
    for sname, src in source_by_name.items():
        for ch in db.get_chunks_by_source(src["id"]):
            key = (sname, ch["page_number"])
            if key in seen:
                continue
            if term_lower in normalize_chunk(ch["content"]).lower():
                seen.add(key)
                chunk_start = time_map.get(key)
                seg_start = resolve_segment_start(segments_by_label, sname, search_term, chunk_start)
                result.append({
                    "source_label": sname,
                    "page_number": ch["page_number"],
                    "start_time": seg_start,
                })
    result.sort(key=lambda s: (
        s.get("source_label", ""),
        s.get("start_time") if s.get("start_time") is not None else (s.get("page_number") or 0),
    ))
    return result
