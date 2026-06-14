"""Context builder for mode='source': pulls chunks/summaries from N sources
and packs them into a budget-limited context string for the LLM prompt."""

from dataclasses import dataclass, field

from src import database as db


@dataclass
class QuelleContext:
    """Collected metadata for mode='source' generation."""
    context: str  # finished LLM context (trimmed)
    first_label: str
    multi_label: str
    source_hint: str  # "folgender Source" / "folgenden Sources"
    source_by_name: dict[str, dict] = field(default_factory=dict)


def build_source_context(uuids: list[str], tool: str) -> QuelleContext | None:
    """Build context string + meta maps from N sources. None = no content available."""
    context_parts: list[str] = []
    first_label = ""
    source_by_name: dict[str, dict] = {}

    # karteikarten generate from broad context, so use ALL chunks; the other tools
    # cap to the first slice per source (then everything is budget-trimmed below).
    use_chunks = tool == "karteikarten"

    for suuid in uuids:
        source = db.get_aia_source(suuid)
        if not source:
            continue
        source_label = source["filename"]
        source_by_name[source_label] = source
        if not first_label:
            first_label = source_label

        chunks = db.get_chunks_by_source(source["id"])
        if not chunks:
            continue
        if not use_chunks:
            chunks = chunks[:30]
        parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks]
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
        source_by_name=source_by_name,
    )


