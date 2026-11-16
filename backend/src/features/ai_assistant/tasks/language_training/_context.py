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


def build_source_context(uuids: list[str], tool: str, count: int,
                         *, with_quota: bool = True) -> QuelleContext | None:
    """Builds the context from several sources, greedily and sweeping.

    ``count`` is how many exercises are wanted, it sizes the context. A tool
    whose result is one continuous text passes ``with_quota=False``, a quota
    would break that text apart.
    """
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
        workspace_id, tool, count)
    picked_by_label = [(label, picked) for _sid, label, picked in gefuellt]
    if not picked_by_label:
        return None

    quota = (per_section_quota(len(picked_by_label), count)
             if with_quota and count >= len(picked_by_label) else 0)
    return _assemble(picked_by_label, source_by_name, quota)


def build_context_from_chunks(uuids: list[str], chunks: list[dict]) -> QuelleContext | None:
    """The context from found spots instead of a sweep, a source without a hit stays out."""
    by_id: dict[int, dict] = {}
    for suuid in uuids:
        source = db.get_aia_source(suuid)
        if source:
            by_id[source["id"]] = source
    je_quelle: dict[int, list[dict]] = {}
    for chunk in chunks:
        sid = chunk.get("source_id")
        if sid in by_id and (chunk.get("content") or "").strip():
            je_quelle.setdefault(sid, []).append(chunk)
    # In the order the person chose, so the section numbers stay calm.
    picked_by_label = [(by_id[sid]["filename"], je_quelle[sid]) for sid in by_id if sid in je_quelle]
    if not picked_by_label:
        return None
    source_by_name = {by_id[sid]["filename"]: by_id[sid] for sid in by_id if sid in je_quelle}
    return _assemble(picked_by_label, source_by_name, quota=0)


def _assemble(picked_by_label: list[tuple[str, list[dict]]],
              source_by_name: dict[str, dict], quota: int) -> QuelleContext:
    """The finished context out of the chosen chunks, one numbered section per source."""
    # The material can name sources the selection lost to the budget.
    first_label = picked_by_label[0][0]
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


def label_for_sources(uuids: list[str]) -> str:
    """The same name as ``multi_label``, for callers that build no context."""
    try:
        namen = [(db.get_aia_source(u) or {}).get("filename") or "" for u in uuids]
    except Exception:  # noqa: BLE001 - a name is worth no failed set
        return ""
    namen = [n for n in namen if n]
    if not namen:
        return ""
    return namen[0] if len(namen) == 1 else f"{len(namen)} Sources"
