"""Builds the context from several sources and sweeps a different window each run."""

from dataclasses import dataclass, field

from src import database as db
from src.features.ai_assistant.tasks._context_budget import fill_sources_greedy


@dataclass
class QuelleContext:
    """Collected metadata for mode='source' generation."""
    context: str  # finished LLM context (trimmed)
    first_label: str
    multi_label: str
    source_hint: str  # "folgender Source" / "folgenden Sources"
    source_by_name: dict[str, dict] = field(default_factory=dict)
    # Section number to file name, that makes the coverage measurable.
    sections: dict[int, str] = field(default_factory=dict)
    # The pages the model really saw, the citations stay limited to them.
    seen_pages_by_source: dict[int, set] = field(default_factory=dict)
    # Segment number to timestamp, media only, so the chip can jump.
    media_start_by_page: dict[int, dict[int, float]] = field(default_factory=dict)


def per_section_quota(n_sections: int, count: int) -> int:
    """How many entries each section owes. At least one, so a section is never optional."""
    return max(1, count // n_sections) if n_sections else 0


def quota_fits(ctx: "QuelleContext", count: int) -> bool:
    """Whether a per-section quota is possible at all with this many entries."""
    return 2 <= len(ctx.sections) <= count


def coverage_rule(ctx: "QuelleContext", count: int) -> str:
    """Prompt block that spreads the exercises across all sections."""
    if not quota_fits(ctx, count):
        return ""
    quota = per_section_quota(len(ctx.sections), count)
    listing = "\n".join(f"  {num} = {label}" for num, label in sorted(ctx.sections.items()))
    return (
        f"\n\nCOVERAGE. The source material is split into {len(ctx.sections)} numbered "
        f"sections of equal size:\n{listing}\n"
        f"Take at least {quota} of the {count} entries from EACH section. Every section "
        "must be used. Never build the whole set out of one section, however rich it "
        "looks, and make every entry recognisably about ITS OWN section's content.\n"
        'Add "section": <the section number> to every entry you write, so the split is '
        "visible in your answer."
    )


def section_usage(items: list[dict], ctx: "QuelleContext") -> dict[int, int]:
    """How many exercises came out of each section, according to the model."""
    used = {num: 0 for num in ctx.sections}
    for item in items:
        try:
            num = int(item.get("_section"))
        except (TypeError, ValueError):
            continue
        if num in used:
            used[num] += 1
    return used


def missing_section_uuids(items: list[dict], ctx: "QuelleContext") -> list[str]:
    """The sources of the sections that got nothing, in section order."""
    usage = section_usage(items, ctx)
    if not any(usage.values()):
        return []
    out = []
    for num in sorted(ctx.sections):
        if usage.get(num):
            continue
        source = ctx.source_by_name.get(ctx.sections[num]) or {}
        if source.get("uuid"):
            out.append(source["uuid"])
    return out


def remap_sections(items: list[dict], from_ctx: "QuelleContext",
                   to_ctx: "QuelleContext") -> list[dict]:
    """Maps the section numbers of a top-up back into the full numbering."""
    back = {label: num for num, label in to_ctx.sections.items()}
    for item in items:
        try:
            num = int(item.get("_section"))
        except (TypeError, ValueError):
            item["_section"] = None
            continue
        item["_section"] = back.get(from_ctx.sections.get(num))
    return items


def rebalance_to_count(items: list[dict], count: int) -> list[dict]:
    """Trims back after a top-up, the fullest sections give up first."""
    if len(items) <= count:
        return items
    keep = list(items)
    while len(keep) > count:
        usage: dict[object, int] = {}
        for item in keep:
            usage[item.get("_section")] = usage.get(item.get("_section"), 0) + 1
        # None first, then whichever section is most over-served.
        fullest = max(usage, key=lambda s: (s is None, usage[s]))
        for i in range(len(keep) - 1, -1, -1):
            if keep[i].get("_section") == fullest:
                keep.pop(i)
                break
        else:
            keep.pop()
    return keep


def build_source_context(uuids: list[str], tool: str,
                         count: int | None = None) -> QuelleContext | None:
    """Builds the context from several sources, greedily and sweeping."""
    sources: list[tuple[str, list[dict]]] = []
    source_by_name: dict[str, dict] = {}
    first_label = ""

    for suuid in uuids:
        source = db.get_aia_source(suuid)
        if not source:
            continue
        chunks = db.get_chunks_by_source(source["id"])
        if not chunks:
            continue
        label = source["filename"]
        source_by_name[label] = source
        if not first_label:
            first_label = label
        sources.append((label, chunks))

    if not sources:
        return None

    workspace_id = source_by_name[first_label].get("workspace_id")
    # Every source takes what is left of the budget, whoever comes too late falls away.
    gefuellt = fill_sources_greedy(
        [(source_by_name[label]["id"], label, chunks) for label, chunks in sources],
        workspace_id, tool)
    picked_by_label = [(label, picked) for _sid, label, picked in gefuellt]
    if not picked_by_label:
        return None

    # The material can name sources the selection lost to the budget.
    first_label = picked_by_label[0][0]
    quota = (per_section_quota(len(picked_by_label), count)
             if count and count >= len(picked_by_label) else 0)
    trimmed: list[str] = []
    seen_pages_by_source: dict[int, set] = {}
    media_start_by_page: dict[int, dict] = {}
    sections: dict[int, str] = {}
    for i, (label, picked) in enumerate(picked_by_label, start=1):
        sections[i] = label
        lines = [f"[{label}, S. {c['page_number']}] {c['content']}" for c in picked]
        if len(picked_by_label) > 1:
            # The quota sits in the header of every section, next to the material.
            head = f"=== SECTION {i} OF {len(picked_by_label)} — {label}"
            if quota:
                head += f" — take at least {quota} entries from here"
            head += " ==="
        else:
            head = f"--- {label} ---"
        trimmed.append(head + "\n" + "\n".join(lines))
        sid = source_by_name[label]["id"]
        # The shown pages, for media only the source counts.
        seen_pages_by_source.setdefault(sid, set()).update(c["page_number"] for c in picked)
        # Segment number to timestamp so a citation becomes a play position.
        times = {c["page_number"]: c["start_time"] for c in picked
                 if c.get("start_time") is not None}
        if times:
            media_start_by_page.setdefault(sid, {}).update(times)

    einzeln = len(picked_by_label) == 1
    multi_label = first_label if einzeln else f"{len(picked_by_label)} Sources"
    source_hint = "folgender Source" if einzeln else "folgenden Sources"

    return QuelleContext(
        context="\n\n".join(trimmed),
        first_label=first_label,
        multi_label=multi_label,
        source_hint=source_hint,
        sections=sections,
        source_by_name=source_by_name,
        seen_pages_by_source=seen_pages_by_source,
        media_start_by_page=media_start_by_page,
    )
