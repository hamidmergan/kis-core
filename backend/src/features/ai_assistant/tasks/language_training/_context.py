"""Context-Builder für mode='quelle': zieht Chunks/Summaries aus N Quellen
und packt sie in einen budget-begrenzten Kontext-String für den LLM-Prompt."""

from dataclasses import dataclass, field

from src import database as db

from src.features.ki_assistent.tasks.sprachtraining._text_utils import (
    normalize_for_segment_lookup,
)


@dataclass
class QuelleContext:
    """Gesammelte Metadaten für mode='quelle' Generierung."""
    context: str  # fertiger LLM-Kontext (trimmed)
    first_label: str
    multi_label: str
    source_hint: str  # "folgender Quelle" / "folgenden Quellen"
    time_map: dict[tuple[str, int], float] = field(default_factory=dict)
    source_by_name: dict[str, dict] = field(default_factory=dict)
    segments_by_label: dict[str, list[dict]] = field(default_factory=dict)


def build_quelle_context(uuids: list[str], tool: str) -> QuelleContext | None:
    """Baut Kontext-String + Meta-Maps aus N Quellen. None = keine Inhalte verfügbar."""
    context_parts: list[str] = []
    first_label = ""
    time_map: dict[tuple[str, int], float] = {}
    source_by_name: dict[str, dict] = {}
    segments_by_label: dict[str, list[dict]] = {}

    # karteikarten braucht Raw-Chunks (LLM zitiert wörtlich für Evidence-Validierung)
    # alle anderen Tools nutzen Page-Summaries (schneller, dichter)
    use_chunks = tool == "karteikarten"

    for suuid in uuids:
        source = db.get_kia_source(suuid)
        if not source:
            continue
        source_label = source["filename"]
        source_by_name[source_label] = source
        if not first_label:
            first_label = source_label

        chunks_all = db.get_chunks_by_source(source["id"]) if use_chunks else None
        summaries = None if use_chunks else db.get_paragraph_summaries_by_source(source["id"])

        if use_chunks and chunks_all:
            for c in chunks_all:
                if c.get("start_time") is not None:
                    time_map[(source_label, c["page_number"])] = c["start_time"]
            # Whisper-Segmente laden für Sub-Chunk-Timestamp-Auflösung bei Media-Quellen
            if any(c.get("start_time") is not None for c in chunks_all):
                from src.features.ki_assistent.routes._helpers import _load_transcript_segments
                segments_by_label[source_label] = _load_transcript_segments(source)
            parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks_all]
            context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))
        elif summaries:
            pages_map: dict[int, list[str]] = {}
            for s in summaries:
                pages_map.setdefault(s["page_number"], []).append(s["summary"])
            parts = [f"[{source_label}, S. {p}] {' '.join(texts)}" for p, texts in sorted(pages_map.items())]
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

    # Fair budget split: 200k Zeichen total, ganze Zeilen
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

    multi_label = first_label if len(uuids) == 1 else f"{len(uuids)} Quellen"
    source_hint = "folgender Quelle" if len(uuids) == 1 else "folgenden Quellen"

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
    """Für Media-Quellen: suche das Whisper-Segment, das die Evidence enthält, und
    gib dessen start_time zurück. Fallback auf den Chunk-start_time wenn kein Match.

    Ohne diese Auflösung würde ein ~1000-Zeichen-Chunk, der 60-120s abdeckt, allen
    Citations den gleichen Startzeitpunkt geben statt des Moments des Zitats.
    """
    segments = segments_by_label.get(source_label) or []
    if not segments or not evidence:
        return fallback

    ev = normalize_for_segment_lookup(evidence)
    if not ev:
        return fallback

    # Sliding-window: finde Segment, dessen normalisierter Text mit dem Evidence-Anfang
    # maximal überlappt (die ersten Wörter sagen, wo das Zitat beginnt)
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
        # Evidence spannt möglicherweise Segment-Grenze: Suffix-Match + Nachbar-Prefix
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
    """Findet alle Seiten (über alle Quellen), in denen search_term im Chunk-Text vorkommt."""
    from src.features.ki_assistent.tasks.sprachtraining._text_utils import normalize_chunk

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
