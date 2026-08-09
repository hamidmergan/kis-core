"""Shared context sizing for the AIA generation tools.

Three jobs, one place so every tool behaves the same:

* ``context_budget()`` — the admin-tunable character budget (``aia_context_max_chars``),
  the SAME setting the chat uses.
* ``tool_context_budget()`` — the separate, usually larger budget for the generation
  tools (``aia_tool_context_max_chars``). A tool packs a whole document into ONE call,
  the chat pays its budget on every single question.
* ``select_chunks_for_budget()`` — pick which chunks of a source go into that budget.
  A source that fits goes in whole. A source that is too big is read as a SWEEP: the
  document is cut into ``_COVERAGE_BLOCKS`` blocks, every run reads a window inside each
  block, and the next run continues where this one stopped.

Why a sweep and not a random sample. Until 2026-08-08 the windows started at a random
offset per run, which looks like variation but is a draw with replacement: nothing
remembers what was already used, so some pages come up again and again while others are
missed for a long time. Two effects, both measured on a real 489-page PDF over 30 runs
against an 800k budget:

* page 1 was seen ONCE. The first block's window started at a random point inside the
  block and only ever grew forward, so everything before that point was unreachable.
* it took 12 runs before every page had been seen at all, and 8 pages were still under
  five hits while others sat at twenty.

The sweep fixes both by construction: full coverage after 3 runs (the arithmetic
minimum for that document at that budget, 2.17M chars / 800k), every page between 10 and
17 hits, page 1 among them. It also needs no randomness at all, so a run is reproducible.
"""

from src.limits import (
    AIA_CONTEXT_MAX_CHARS,
    AIA_CONTEXT_HARD_CAP,
    AIA_TOOL_CONTEXT_MAX_CHARS,
    AIA_TOOL_CONTEXT_HARD_CAP,
)

# How many windows to spread across an oversized document. Each run reads one window per
# block, so a single run still spans the whole document rather than one contiguous slice
# of it — a set of exercises should not be about chapter 3 alone.
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


def select_chunks_for_budget(
    chunks: list[dict], budget: int, *, cursors: list[int] | None = None,
) -> tuple[list[dict], list[int]]:
    """Choose chunks of ONE source to fit ``budget`` characters, and say where to resume.

    * Source fits the budget → all chunks, in document order. Nothing to sweep.
    * Source is too big → one window per block, each starting where the previous run
      stopped. A window that reaches the end of its block wraps around to the block's
      start, so a block is read completely before anything in it repeats.

    ``cursors`` is what the previous run returned; an empty list or ``None`` means a
    first run, which starts at the beginning of every block. The returned chunks are in
    document order, the returned cursors belong to the caller to persist.

    Deliberately free of randomness. The sweep is what produces variation now, and a
    deterministic run is one that can be reproduced from its stored cursors.
    """
    chunks = list(chunks)
    if not chunks:
        return chunks, list(cursors or [])
    total = sum(_len(c) for c in chunks)
    if total <= budget:
        # The whole source goes in, so there is no position to resume from. Reset rather
        # than keep stale cursors: sources grow when a document is re-uploaded.
        return chunks, []

    n = len(chunks)
    blocks = max(1, min(_COVERAGE_BLOCKS, n))
    per_block = max(1, budget // blocks)
    previous = list(cursors or [])
    # A stored list from a different block count (older row, tiny source) is padded or cut
    # rather than discarded, so a changed document costs at most one uneven run.
    previous = (previous + [0] * blocks)[:blocks]

    bounds = [(int(b * n / blocks), max(1, int((b + 1) * n / blocks) - int(b * n / blocks)))
              for b in range(blocks)]
    start = [previous[b] % bounds[b][1] for b in range(blocks)]
    steps = [0] * blocks
    selected: set[int] = set()
    used = 0

    def take(b: int) -> bool:
        """Read one more chunk in block ``b``. False when the block has nothing left."""
        nonlocal used
        lo, width = bounds[b]
        if steps[b] >= width:
            return False
        index = lo + ((start[b] + steps[b]) % width)
        selected.add(index)
        used += _len(chunks[index])
        steps[b] += 1
        return True

    # Every block gets its own share first, so one run always spans the whole document
    # rather than spending the budget on whichever block happens to come first.
    for b in range(blocks):
        lo, width = bounds[b]
        share = 0
        while steps[b] < width:
            index = lo + ((start[b] + steps[b]) % width)
            length = _len(chunks[index])
            # The first chunk of a block is taken even when it alone exceeds the share.
            # Skipping it would park this block's cursor in front of it forever and the
            # material behind it would never be read.
            if steps[b] > 0 and share + length > per_block:
                break
            share += length
            take(b)

    # Whatever the per-block split left over is handed out round-robin, otherwise the
    # remainder of every block's share is wasted and the sweep needs more runs than the
    # budget actually calls for.
    progress = True
    while used < budget and progress:
        progress = False
        for b in range(blocks):
            lo, width = bounds[b]
            if steps[b] >= width:
                continue
            index = lo + ((start[b] + steps[b]) % width)
            if used + _len(chunks[index]) > budget:
                continue
            take(b)
            progress = True

    resume = [(start[b] + steps[b]) % bounds[b][1] for b in range(blocks)]
    return [chunks[i] for i in sorted(selected)], resume


def _len(chunk: dict) -> int:
    """Characters this chunk costs in the context, including its separator."""
    return len(chunk.get("content") or "") + 1


def read_cursors(workspace_id, source_id: int, tool: str) -> list[int]:
    """Where the last run of this tool stopped in this source. Empty = first run.

    A failing read degrades to a first run rather than to an error: losing the sweep
    position costs one repeated window, failing the task costs the whole set.
    """
    if not workspace_id:
        return []
    from src import database as db
    try:
        return db.get_context_cursors(workspace_id, source_id, tool)
    except Exception:  # noqa: BLE001
        return []


def write_cursors(workspace_id, source_id: int, tool: str, cursors: list[int]) -> None:
    """Remember where the next run resumes. Never fails a generation, as above.

    An empty ``cursors`` list means the source fitted the budget whole, so there is no
    position to keep and nothing is written.
    """
    if not workspace_id or not cursors:
        return
    from src import database as db
    try:
        db.set_context_cursors(workspace_id, source_id, tool, cursors)
    except Exception:  # noqa: BLE001
        pass


# ``rotating_focus`` lived here until 2026-08-08. It threw away 45% of the pages that
# survived the budget so that two runs would see different material. The sweep above does
# that job by construction and without discarding anything, so keeping both meant cutting
# an already-cut context a second time: on a 489-page PDF the model ended up with 98 of
# 489 pages instead of 178. Uniqueness of the exercises themselves is not a context
# problem anyway and is handled after generation, in ``language_training._dedup``.
