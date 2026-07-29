"""Context builder for mode='source': pulls chunks from N sources and packs them into a
budget-limited, per-run-rotating context string for the LLM prompt."""

import random
from dataclasses import dataclass, field

from src import database as db
from src.features.ai_assistant.tasks._context_budget import (
    tool_context_budget,
    select_chunks_for_budget,
    rotating_focus,
)


# A source contributes at least this much even when a tiny one sets the common size.
# Without it a half-page PDF would shrink every other source down to its own size.
_MIN_PER_SOURCE_CHARS = 3000


@dataclass
class QuelleContext:
    """Collected metadata for mode='source' generation."""
    context: str  # finished LLM context (trimmed)
    first_label: str
    multi_label: str
    source_hint: str  # "folgender Source" / "folgenden Sources"
    source_by_name: dict[str, dict] = field(default_factory=dict)
    # Section number -> filename, in the order the sections appear in the context. The
    # model cites these numbers back, which is what makes coverage measurable: the
    # post-hoc attribution cannot tell where an exercise came from when its wording is
    # generic enough to match every source.
    sections: dict[int, str] = field(default_factory=dict)
    # {source_id: set(page_numbers)} actually present in the context above — the pages the
    # LLM really saw. Attribution clamps chips to these (like chat's seen-check), so a card
    # can never cite a page the model was not shown. Media source_ids appear here too (their
    # seen-check is source-level, not per page).
    seen_pages_by_source: dict[int, set] = field(default_factory=dict)


def per_section_quota(n_sections: int, count: int) -> int:
    """How many entries each section owes. At least one, so a section is never optional."""
    return max(1, count // n_sections) if n_sections else 0


def coverage_rule(ctx: "QuelleContext", count: int) -> str:
    """Prompt block that spreads the entries over every section of the context.

    Two earlier attempts were not enough. Splitting the character budget per source only
    guarantees all of them are IN the context, and it does not even do that evenly: the
    split is a ceiling, so a one-hour transcript filled 39% of the context and a slide
    deck 8%, and the model wrote about the transcript. A quota stated once at the top of
    the prompt then landed 4 of 5 sources, still lopsided.

    So the quota is repeated in the header of every section, right where the material is,
    and each entry has to name the section it came from. Naming it forces the model to
    count instead of estimate, and it makes the result checkable afterwards -- the
    post-hoc attribution cannot do that, because a generic sentence matches every source.

    Empty for a single section, where there is nothing to spread.
    """
    if len(ctx.sections) < 2:
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
    """How many entries each section got, by the model's own ``_section`` claim.

    Sections with nothing map to 0, so a caller can see at a glance which ones were
    skipped. Unknown numbers are dropped rather than trusted.

    Deliberately the model's claim and not the post-hoc attribution: attribution matches
    a finished sentence against the whole workspace, and a sentence like "Die Studierenden
    zitieren korrekt" fits every source, so it says nothing about where the model looked.
    """
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
    """Source uuids of the sections that got nothing, in section order.

    Feeds the top-up run. Measured need: the grammar tool served all five sections on
    its own, the quiz skipped the last one in both runs, so this is not hypothetical
    and not worth an extra call when it does not happen.

    A run that names NO section at all yields nothing to top up. The model does skip the
    field sometimes, and reading that as "every section was missed" cost a full second
    generation that could not know any better than the first.
    """
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
    """Renumber a top-up run's ``_section`` claims into the full context's numbering.

    The top-up sees only the skipped sources, so it numbers them 1..n again. Merged
    unchanged, its "section 1" would read as the full context's section 1 and the
    rebalancing would drop the wrong entries. The filename is what actually identifies
    a section, so it is the bridge.
    """
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
    """Trim back to ``count`` after a top-up, dropping from the fullest sections first.

    The learner asked for a fixed number of entries, so the top-up must not simply make
    the set longer. Entries whose section is unknown are dropped before the known ones,
    since they cannot be shown to serve any section.
    """
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


def _chunk_len(chunk: dict) -> int:
    return len(chunk.get("content") or "") + 1


def _trim_to_size(chunks: list[dict], cap: int, rng) -> list[dict]:
    """Cut a source down to ``cap`` characters without favouring the front.

    Taking the first chunks until the cap is reached would always keep the beginning of
    the document. The pages are drawn at random first, then put back in reading order,
    so the excerpt still stays coherent to read.
    """
    if sum(_chunk_len(c) for c in chunks) <= cap:
        return chunks
    order = list(chunks)
    rng.shuffle(order)
    kept, size = [], 0
    for chunk in order:
        length = _chunk_len(chunk)
        if size + length > cap:
            continue
        kept.append(chunk)
        size += length
    return sorted(kept, key=lambda c: c["page_number"])


def build_source_context(uuids: list[str], tool: str,
                         count: int | None = None) -> QuelleContext | None:
    """Build context string + meta maps from N sources. None = no content available.

    Three things shape what the model sees:

    * budget — a source goes in whole when it fits the admin ``aia_tool_context_max_chars``
      budget (shared by all generation tools, separate from the chat budget), otherwise it is
      sampled as contiguous windows spread across the whole document (``select_chunks_for_budget``).
    * rotation — each run then keeps only a subset of the pages, rotating AWAY from the pages
      that were just questioned (``rotating_focus`` + ``get_recent_exercise_pages``). This is a
      HARD restriction on the context, not a prompt hint: the model demonstrably ignores a soft
      "focus on these pages" instruction and reproduces the same salient questions, so we
      instead change the chunks it is actually given. Across runs the whole document is
      covered; within one run the model can't rehash the previous set.
    * equal sections — with several sources every one of them is then cut to the SAME size
      and gets a numbered header. Without that step the per-source budget is only a
      ceiling: each source contributes its own length, so a one-hour transcript took 39%
      of the context against a slide deck's 8%, and the exercises were about the
      transcript. Equal sections cost total volume, which is fine here because a handful
      of exercises needs far less material than a whole document.

    ``count`` is the number of entries being generated. It only appears in the section
    headers as the per-section quota, so the requirement stands next to the material
    instead of only at the top of the prompt.
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
    recent_pages = db.get_recent_exercise_pages(workspace_id, tool) if workspace_id else []

    budget_per_source = max(1000, tool_context_budget() // len(sources))
    rng = random.Random()  # fresh per run -> different sampling/rotation each generation

    picked_by_label: list[tuple[str, list[dict]]] = []
    for label, chunks in sources:
        picked = select_chunks_for_budget(chunks, budget_per_source, rng=rng)
        # Rotate this run's pages away from recently-questioned ones (variation lever for the
        # common case where the whole document fits and the chunk set is otherwise identical).
        #
        # TODO ANPASSEN (hardcodiert): Anders als Mindmap und Datentabelle sehen die
        # Uebungs-Tools (Karteikarten, Flashcards, Quiz, Lueckentext, Begriffe) hier NICHT
        # den vollen Dateikontext, sondern pro Lauf nur ein rotierendes Subset von rund 55
        # Prozent der Seiten (rotating_focus fraction=0.55, min_keep=4). Diese Werte stehen
        # fest im Code und sind ueber kein Admin-Setting steuerbar. Wir muessen das System
        # anpassen: die Fraction konfigurierbar machen oder das Verhalten an Mindmap und
        # Datentabelle angleichen (voller Kontext), je nachdem was didaktisch gewollt ist.
        pages_here = [c["page_number"] for c in picked]
        keep = set(rotating_focus(pages_here, recent=recent_pages, rng=rng))
        picked_by_label.append((label, [c for c in picked if c["page_number"] in keep]))

    # Equal sections. The smallest source sets the size, with a floor so one very short
    # document cannot starve the rest. Single source: nothing to balance.
    if len(picked_by_label) > 1:
        sizes = [sum(_chunk_len(c) for c in chunks) for _, chunks in picked_by_label if chunks]
        cap = max(_MIN_PER_SOURCE_CHARS, min(sizes)) if sizes else _MIN_PER_SOURCE_CHARS
        picked_by_label = [(label, _trim_to_size(chunks, cap, rng))
                           for label, chunks in picked_by_label]

    quota = per_section_quota(len(picked_by_label), count) if count else 0
    trimmed: list[str] = []
    seen_pages_by_source: dict[int, set] = {}
    sections: dict[int, str] = {}
    for i, (label, picked) in enumerate(picked_by_label, start=1):
        sections[i] = label
        lines = [f"[{label}, S. {c['page_number']}] {c['content']}" for c in picked]
        if len(picked_by_label) > 1:
            # The quota rides in the header, next to the material it applies to. Stated
            # only once at the top of the prompt it reached 4 of 5 sources, lopsided.
            head = f"=== SECTION {i} OF {len(picked_by_label)} — {label}"
            if quota:
                head += f" — take at least {quota} entries from here"
            head += " ==="
        else:
            head = f"--- {label} ---"
        trimmed.append(head + "\n" + "\n".join(lines))
        sid = source_by_name[label]["id"]
        # The pages the LLM was actually shown (used as the attribution seen-set). Media
        # chunks land here too: their page_number is a segment index, but the seen-check is
        # source-level for media, so recording the source_id is what matters.
        seen_pages_by_source.setdefault(sid, set()).update(c["page_number"] for c in picked)

    multi_label = first_label if len(uuids) == 1 else f"{len(uuids)} Sources"
    source_hint = "folgender Source" if len(uuids) == 1 else "folgenden Sources"

    return QuelleContext(
        context="\n\n".join(trimmed),
        first_label=first_label,
        multi_label=multi_label,
        source_hint=source_hint,
        sections=sections,
        source_by_name=source_by_name,
        seen_pages_by_source=seen_pages_by_source,
    )
