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


@dataclass
class QuelleContext:
    """Collected metadata for mode='source' generation."""
    context: str  # finished LLM context (trimmed)
    first_label: str
    multi_label: str
    source_hint: str  # "folgender Source" / "folgenden Sources"
    source_by_name: dict[str, dict] = field(default_factory=dict)
    # {source_id: set(page_numbers)} actually present in the context above — the pages the
    # LLM really saw. Attribution clamps chips to these (like chat's seen-check), so a card
    # can never cite a page the model was not shown. Media source_ids appear here too (their
    # seen-check is source-level, not per page).
    seen_pages_by_source: dict[int, set] = field(default_factory=dict)


def build_source_context(uuids: list[str], tool: str) -> QuelleContext | None:
    """Build context string + meta maps from N sources. None = no content available.

    Two things keep the exercises varied (the user's "nicht immer die gleichen Fragen / nicht
    die gleichen Chunks"):

    * budget — a source goes in whole when it fits the admin ``aia_tool_context_max_chars``
      budget (shared by all generation tools, separate from the chat budget), otherwise it is
      sampled as contiguous windows spread across the whole document (``select_chunks_for_budget``).
    * rotation — each run then keeps only a subset of the pages, rotating AWAY from the pages
      that were just questioned (``rotating_focus`` + ``get_recent_exercise_pages``). This is a
      HARD restriction on the context, not a prompt hint: the model demonstrably ignores a soft
      "focus on these pages" instruction and reproduces the same salient questions, so we
      instead change the chunks it is actually given. Across runs the whole document is
      covered; within one run the model can't rehash the previous set.
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

    trimmed: list[str] = []
    seen_pages_by_source: dict[int, set] = {}
    for label, chunks in sources:
        picked = select_chunks_for_budget(chunks, budget_per_source, rng=rng)
        # Rotate this run's pages away from recently-questioned ones (variation lever for the
        # common case where the whole document fits and the chunk set is otherwise identical).
        pages_here = [c["page_number"] for c in picked]
        keep = set(rotating_focus(pages_here, recent=recent_pages, rng=rng))
        picked = [c for c in picked if c["page_number"] in keep]
        lines = [f"[{label}, S. {c['page_number']}] {c['content']}" for c in picked]
        trimmed.append(f"--- {label} ---\n" + "\n".join(lines))
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
        source_by_name=source_by_name,
        seen_pages_by_source=seen_pages_by_source,
    )
