"""Context builder for mode='source': pulls chunks/summaries from N sources
and packs them into a budget-limited context string for the LLM prompt."""

import re
from dataclasses import dataclass, field

from src import database as db
from src.limits import AIA_CONTEXT_MAX_CHARS, AIA_CONTEXT_HARD_CAP

# Marker each context line starts with: ``[<filename>, S. <page>] <content>``.
_CONTEXT_MARKER = re.compile(r"^\[(.+?),\s*S\.\s*(\d+)\]")


def _context_budget() -> int:
    """Character budget for the LLM context, admin-tunable via ``aia_context_max_chars``.

    Mirrors the chat's budget resolver so the tools honour the SAME admin setting instead
    of a hardcoded value (a deployment on a small local model vs a large cloud model needs
    different budgets). Falls back to AIA_CONTEXT_MAX_CHARS and is clamped to the hard cap."""
    try:
        value = int(db.get_setting("aia_context_max_chars", str(AIA_CONTEXT_MAX_CHARS)))
    except (ValueError, TypeError):
        return AIA_CONTEXT_MAX_CHARS
    return max(1000, min(value, AIA_CONTEXT_HARD_CAP))


@dataclass
class QuelleContext:
    """Collected metadata for mode='source' generation."""
    context: str  # finished LLM context (trimmed)
    first_label: str
    multi_label: str
    source_hint: str  # "folgender Source" / "folgenden Sources"
    source_by_name: dict[str, dict] = field(default_factory=dict)
    # {source_id: set(page_numbers)} actually present in the trimmed context above — the
    # pages the LLM really saw. Attribution clamps chips to these (like chat's seen-check),
    # so a card can never cite a page the model was not shown. Media source_ids appear here
    # too (their seen-check is source-level, not per page).
    seen_pages_by_source: dict[int, set] = field(default_factory=dict)


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

    # Fair budget split across sources, whole lines. Budget = admin aia_context_max_chars.
    budget_per_source = _context_budget() // len(context_parts)
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

    # Record which source/page actually survived into the trimmed context — the set the
    # LLM was shown. Parsed from the final text so it matches byte-for-byte what it read.
    seen_pages_by_source: dict[int, set] = {}
    for block in trimmed:
        for line in block.split("\n"):
            m = _CONTEXT_MARKER.match(line)
            if not m:
                continue
            src = source_by_name.get(m.group(1))
            if src:
                seen_pages_by_source.setdefault(src["id"], set()).add(int(m.group(2)))

    return QuelleContext(
        context="\n\n".join(trimmed),
        first_label=first_label,
        multi_label=multi_label,
        source_hint=source_hint,
        source_by_name=source_by_name,
        seen_pages_by_source=seen_pages_by_source,
    )


