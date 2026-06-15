"""Shared context sizing for the AIA generation tools.

Two jobs, one place so every tool behaves the same:

* ``context_budget()`` — the admin-tunable character budget (``aia_context_max_chars``),
  the SAME setting the chat uses. No tool hardcodes its own number anymore.
* ``select_chunks_for_budget()`` — pick which chunks of a source go into that budget.
  A source that fits goes in whole. A source that is too big is sampled as a handful of
  contiguous windows spread across the WHOLE document (not just the front) with a random
  jitter per run, so (a) the whole document is covered and (b) two runs see different
  material and therefore produce different exercises.
"""

import random

from src.limits import (
    AIA_CONTEXT_MAX_CHARS,
    AIA_CONTEXT_HARD_CAP,
    AIA_TOOL_CONTEXT_MAX_CHARS,
    AIA_TOOL_CONTEXT_HARD_CAP,
)

# How many contiguous windows to spread across an oversized document. Each window grows
# forward from an evenly-spaced, per-run-jittered anchor until the shared budget is full.
_COVERAGE_BLOCKS = 12


def context_budget() -> int:
    """Character budget for the LLM context, admin-tunable via ``aia_context_max_chars``.

    Mirrors the chat's budget resolver so the tools honour the SAME admin setting instead
    of a hardcoded value (a small local model vs a large cloud model wants different
    budgets). Falls back to AIA_CONTEXT_MAX_CHARS, clamped to the hard cap."""
    from src import database as db
    try:
        value = int(db.get_setting("aia_context_max_chars", str(AIA_CONTEXT_MAX_CHARS)))
    except (ValueError, TypeError):
        return AIA_CONTEXT_MAX_CHARS
    return max(1000, min(value, AIA_CONTEXT_HARD_CAP))


def tool_context_budget() -> int:
    """Character budget for the GENERATION TOOLS (mindmap, data table, quiz, flashcards, …).

    A SEPARATE knob from the chat budget (:func:`context_budget`): a tool packs a whole
    document into ONE generation call, so an admin wants to give the tools a larger window
    than every chat turn gets. The caller divides this by the number of selected sources.
    Admin-tunable via ``aia_tool_context_max_chars``, falls back to AIA_TOOL_CONTEXT_MAX_CHARS,
    clamped to the (higher) tool hard cap."""
    from src import database as db
    try:
        value = int(db.get_setting("aia_tool_context_max_chars", str(AIA_TOOL_CONTEXT_MAX_CHARS)))
    except (ValueError, TypeError):
        return AIA_TOOL_CONTEXT_MAX_CHARS
    return max(1000, min(value, AIA_TOOL_CONTEXT_HARD_CAP))


def select_chunks_for_budget(chunks: list[dict], budget: int, *, rng=None) -> list[dict]:
    """Choose chunks of ONE source to fit ``budget`` characters.

    * Source fits the budget → all chunks, in document order.
    * Source is too big → ~``_COVERAGE_BLOCKS`` contiguous windows spread across the whole
      document. Each window starts at an evenly-spaced anchor with a random jitter (``rng``),
      so coverage reaches the end of the document AND two runs sample different material →
      different exercises. The selected chunks are returned in document order.

    ``rng`` is injectable for deterministic tests; production passes a fresh ``random.Random``."""
    chunks = list(chunks)
    if not chunks:
        return chunks
    total = sum(len(c.get("content") or "") + 1 for c in chunks)
    if total <= budget:
        return chunks

    rng = rng or random.Random()
    n = len(chunks)
    blocks = max(1, min(_COVERAGE_BLOCKS, n))
    slot = n / blocks
    cursors: list[int] = []
    for b in range(blocks):
        lo = int(b * slot)
        hi = int((b + 1) * slot)
        cursors.append(rng.randrange(lo, hi) if hi > lo else lo)

    selected: set[int] = set()
    size = 0
    while size < budget:
        added = False
        for i in range(blocks):
            while cursors[i] < n and cursors[i] in selected:
                cursors[i] += 1
            c = cursors[i]
            if c >= n:
                continue
            clen = len(chunks[c].get("content") or "") + 1
            if size + clen > budget:
                continue
            selected.add(c)
            size += clen
            cursors[i] += 1
            added = True
        if not added:
            break
    return [chunks[i] for i in sorted(selected)]


def rotating_focus(pages, recent=None, rng=None, *, fraction: float = 0.55,
                   min_keep: int = 4) -> list[int]:
    """Pick which pages THIS run's context keeps, rotating away from recently-used pages.

    When a whole document fits the budget the chunk set is identical every run, so two runs
    would see the same text and produce the same questions. We instead send only a subset of
    pages each run (a HARD restriction, because the model ignores a soft "focus on …" hint),
    preferring pages NOT in ``recent`` (the pages just questioned). Over several runs the
    document is fully covered, but no single run rehashes the last one.

    Returns the pages to KEEP, sorted. With too few pages it returns them all (no restriction
    worth making). ``recent`` is the page list from :func:`get_recent_exercise_pages`."""
    pages = sorted(set(pages))
    if len(pages) < min_keep + 1:  # <=4 distinct pages: restricting would barely differ
        return pages
    rng = rng or random.Random()
    k = min(len(pages), max(min_keep, round(len(pages) * fraction)))

    recent_set = set(recent or [])
    fresh = [p for p in pages if p not in recent_set]
    used = [p for p in pages if p in recent_set]
    rng.shuffle(fresh)
    rng.shuffle(used)
    chosen = (fresh + used)[:k]  # under-used pages first, top up with used ones if needed
    return sorted(chosen)
