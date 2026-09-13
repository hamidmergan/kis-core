"""Context size for the generating tools: two budgets and the chunk selection."""

from src.limits import (
    AIA_CONTEXT_MAX_CHARS,
    AIA_CONTEXT_HARD_CAP,
    AIA_SPECIFIC_MAX_CHARS,
    AIA_TOOL_CONTEXT_MAX_CHARS,
    AIA_TOOL_CONTEXT_HARD_CAP,
)

# An oversized document is split into this many blocks, one window per block per run.
_COVERAGE_BLOCKS = 12


def context_budget() -> int:
    """Character budget for the context, the same admin setting as in the chat."""
    from src import database as db
    try:
        value = int(db.get_setting("aia_context_max_chars", str(AIA_CONTEXT_MAX_CHARS)))
    except (ValueError, TypeError):
        value = AIA_CONTEXT_MAX_CHARS
    return max(1000, min(value, AIA_CONTEXT_HARD_CAP))


def tool_context_budget() -> int:
    """Its own, usually larger budget for the generating tools."""
    from src import database as db
    try:
        value = int(db.get_setting("aia_tool_context_max_chars", str(AIA_TOOL_CONTEXT_MAX_CHARS)))
    except (ValueError, TypeError):
        value = AIA_TOOL_CONTEXT_MAX_CHARS
    return max(1000, min(value, AIA_TOOL_CONTEXT_HARD_CAP))


def specific_context_budget() -> int:
    """Character budget for a specific question, here less is better than more."""
    from src import database as db
    try:
        value = int(db.get_setting("aia_specific_max_chars", str(AIA_SPECIFIC_MAX_CHARS)))
    except (ValueError, TypeError):
        value = AIA_SPECIFIC_MAX_CHARS
    return max(1000, min(value, AIA_CONTEXT_HARD_CAP))


def select_chunks_for_budget(
    chunks: list[dict], budget: int, *, cursors: list[int] | None = None,
) -> tuple[list[dict], list[int]]:
    """Picks a source's chunks for the budget and says where the next run continues."""
    chunks = list(chunks)
    if not chunks:
        return chunks, list(cursors or [])
    total = sum(_len(c) for c in chunks)
    if total <= budget:
        # If the source fits entirely there is no position to remember.
        return chunks, []

    n = len(chunks)
    blocks = max(1, min(_COVERAGE_BLOCKS, n))
    per_block = max(1, budget // blocks)
    previous = list(cursors or [])
    # A list with a different block count is adjusted instead of thrown away.
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

    # Every block gets its share first so one run touches the whole document.
    for b in range(blocks):
        lo, width = bounds[b]
        share = 0
        while steps[b] < width:
            index = lo + ((start[b] + steps[b]) % width)
            length = _len(chunks[index])
            # The first chunk of a block comes along, otherwise the mark sits before it forever.
            if steps[b] > 0 and share + length > per_block:
                break
            share += length
            take(b)

    # The rest is handed out round robin, otherwise a sweep needs more runs than necessary.
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


# Below this much room a source only adds noise, the list is cut off there.
_MIN_PER_SOURCE_CHARS = 3000


def fill_sources_greedy(
    sources: list[tuple[int, str, list[dict]]], workspace_id, tool: str,
) -> list[tuple[int, str, list[dict]]]:
    """Fills the budget source by source, whoever comes too late falls away.

    Starts where the last run stopped, so over several runs every source gets
    its turn. Inside a source the sweep and its marks stay untouched.
    """
    budget = tool_context_budget()
    order = _rotated(sources, read_rotation(workspace_id, tool))

    taken: dict[int, list[dict]] = {}
    left = budget
    next_start: int | None = None
    for source_id, _label, chunks in order:
        if not chunks:
            continue
        if taken and left < _MIN_PER_SOURCE_CHARS:
            next_start = source_id
            break
        picked, resume = select_chunks_for_budget(
            chunks, left, cursors=read_cursors(workspace_id, source_id, tool))
        write_cursors(workspace_id, source_id, tool, resume)
        if not picked:
            next_start = source_id
            break
        taken[source_id] = picked
        left -= sum(_len(c) for c in picked)

    write_rotation(workspace_id, tool, next_start)
    # Back into the order the person chose, so the section numbers stay calm.
    return [(sid, label, taken[sid]) for sid, label, _chunks in sources if sid in taken]


def _rotated(sources: list[tuple[int, str, list[dict]]],
             start_source_id: int | None) -> list[tuple[int, str, list[dict]]]:
    """The list turned so it begins at ``start_source_id``, else unchanged."""
    if start_source_id is None:
        return list(sources)
    for i, (source_id, _label, _chunks) in enumerate(sources):
        if source_id == start_source_id:
            return list(sources[i:]) + list(sources[:i])
    # The mark points at a source that is gone or deselected, start at the front.
    return list(sources)


def read_rotation(workspace_id, tool: str) -> int | None:
    """Which source the next run starts at, None means the front."""
    if not workspace_id:
        return None
    from src import database as db
    try:
        return db.get_context_rotation(workspace_id, tool)
    except Exception:  # noqa: BLE001
        return None


def write_rotation(workspace_id, tool: str, source_id: int | None) -> None:
    """Remembers which source the next run starts at."""
    if not workspace_id:
        return
    from src import database as db
    try:
        db.set_context_rotation(workspace_id, tool, source_id)
    except Exception:  # noqa: BLE001
        pass


def _len(chunk: dict) -> int:
    """Characters this chunk costs in the context, including its separator."""
    return len(chunk.get("content") or "") + 1


def read_cursors(workspace_id, source_id: int, tool: str) -> list[int]:
    """Where the last run stopped, empty means first run."""
    if not workspace_id:
        return []
    from src import database as db
    try:
        return db.get_context_cursors(workspace_id, source_id, tool)
    except Exception:  # noqa: BLE001
        return []


def write_cursors(workspace_id, source_id: int, tool: str, cursors: list[int]) -> None:
    """Remembers where the next run continues."""
    if not workspace_id or not cursors:
        return
    from src import database as db
    try:
        db.set_context_cursors(workspace_id, source_id, tool, cursors)
    except Exception:  # noqa: BLE001
        pass


