"""Context size for the generating tools: the budgets and the chunk selection."""

import re

from src.services import model_limits
from src.limits import (
    AIA_CONTEXT_HARD_CAP,
    AIA_SPECIFIC_MAX_CHARS,
    AIA_TOOL_CONTEXT_MAX_CHARS,
    AIA_TOOL_CONTEXT_HARD_CAP,
    AIA_EXERCISE_CHARS_PER_ITEM,
    AIA_EXERCISE_TOKENS_BASE,
    AIA_EXERCISE_TOKENS_PER_ITEM,
    AIA_OVERVIEW_TOOL_MAX_CHARS,
)

# An oversized document is split into this many blocks, one window per block per run.
_COVERAGE_BLOCKS = 12


def context_budget() -> int:
    """Character budget of the chat for an overview, the one chat field it shares with a specific question.

    The window still caps the two differently, an overview may fill more of it.
    """
    from src import database as db
    try:
        value = int(db.get_setting("aia_specific_max_chars", str(AIA_SPECIFIC_MAX_CHARS)))
    except (ValueError, TypeError):
        value = AIA_SPECIFIC_MAX_CHARS
    return model_limits.cap_for_window(max(1000, min(value, AIA_CONTEXT_HARD_CAP)),
                                       model_limits.CHAT_SHARE)


def tool_context_budget() -> int:
    """Character budget of the overview tools, the same admin field for all of them."""
    return model_limits.cap_for_window(_tool_field(), model_limits.TOOL_SHARE)


def _tool_field() -> int:
    """The admin field of the overview tools, before any model window caps it."""
    from src import database as db
    try:
        value = int(db.get_setting("aia_tool_context_max_chars", str(AIA_TOOL_CONTEXT_MAX_CHARS)))
    except (ValueError, TypeError):
        value = AIA_TOOL_CONTEXT_MAX_CHARS
    return max(1000, min(value, AIA_TOOL_CONTEXT_HARD_CAP))


def small_model() -> bool:
    """True when the window cannot hold the overview budget, the tools then work in smaller steps."""
    return tool_context_budget() < min(AIA_OVERVIEW_TOOL_MAX_CHARS, _tool_field())


def exercise_context_budget(count: int) -> int:
    """What a set of ``count`` exercises needs, the tool field stays the ceiling.

    No setting of its own: a set of five must not read the material of fifteen,
    and the rest of it follows on later runs anyway.
    """
    wanted = max(1, int(count)) * AIA_EXERCISE_CHARS_PER_ITEM
    return max(1000, min(wanted, tool_context_budget()))


def exercise_max_tokens(count: int) -> int:
    """Answer budget of one exercise call, a model that loops is cut off here."""
    return AIA_EXERCISE_TOKENS_BASE + max(1, int(count)) * AIA_EXERCISE_TOKENS_PER_ITEM


def overview_context_budget() -> int:
    """Material of a mind map or a data table, read in one call."""
    return min(AIA_OVERVIEW_TOOL_MAX_CHARS, tool_context_budget())


def specific_context_budget() -> int:
    """Character budget for a specific question, here less is better than more."""
    from src import database as db
    try:
        value = int(db.get_setting("aia_specific_max_chars", str(AIA_SPECIFIC_MAX_CHARS)))
    except (ValueError, TypeError):
        value = AIA_SPECIFIC_MAX_CHARS
    return model_limits.cap_for_window(max(1000, min(value, AIA_CONTEXT_HARD_CAP)),
                                       model_limits.SPECIFIC_SHARE)


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
    # Every block takes at least one chunk, so a small budget gets fewer blocks.
    blocks = max(1, min(_COVERAGE_BLOCKS, n, int(budget * n / total)))
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
    sources: list[tuple[int, str, list[dict]]], workspace_id, tool: str, count: int,
) -> list[tuple[int, str, list[dict]]]:
    """Fills the budget source by source, whoever comes too late falls away.

    Starts where the last run stopped, so over several runs every source gets
    its turn. Inside a source the sweep and its marks stay untouched.
    """
    budget = exercise_context_budget(count)
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


def fill_sources_evenly(
    sources: list[tuple[int, str, list[dict]]], budget: int | None = None,
) -> list[tuple[int, str, list[dict]]]:
    """Every source gets its share of the budget, whoever needs less passes the rest on."""
    budget = budget or tool_context_budget()
    with_content = [(sid, label, chunks) for sid, label, chunks in sources if chunks]
    taken: dict[int, list[dict]] = {}
    left = budget
    open_count = len(with_content)
    # The smallest source first, so its leftover lifts the shares of the bigger ones.
    for source_id, _label, chunks in sorted(
            with_content, key=lambda s: sum(_len(c) for c in s[2])):
        picked, _resume = select_chunks_for_budget(
            chunks, max(1000, left // max(1, open_count)))
        taken[source_id] = picked
        left -= sum(_len(c) for c in picked)
        open_count -= 1
    # Back into the order the person chose, so the section numbers stay calm.
    return [(sid, label, taken[sid]) for sid, label, _chunks in sources if sid in taken]


# A heading is short, stands on its own line and does not end a sentence.
_HEADING_MAX_CHARS = 80
_HEADING_MAX_WORDS = 10


def _is_heading_line(line: str) -> bool:
    """Short, standing alone and not closing a sentence reads like a heading."""
    if not 2 <= len(line) <= _HEADING_MAX_CHARS:
        return False
    if line[-1] in ".!?,;:":
        return False
    if len(line.split()) > _HEADING_MAX_WORDS:
        return False
    return any(ch.isalpha() for ch in line)


# A line coming back on this share of the pages is page chrome, not a heading.
_CHROME_SHARE = 0.5
_DIGITS = re.compile(r"\d+")


def _chrome_patterns(chunks: list[dict]) -> set[str]:
    """The line shapes that repeat page after page, the page number does not count."""
    seiten: dict[str, set] = {}
    for c in chunks:
        seite = c.get("page_number") or c.get("start_time")
        for line in (c.get("content") or "").splitlines():
            line = line.strip()
            if _is_heading_line(line):
                seiten.setdefault(_DIGITS.sub("#", line), set()).add(seite)
    gesamt = len({c.get("page_number") or c.get("start_time") for c in chunks})
    return {muster for muster, wo in seiten.items()
            if len(wo) > 2 and len(wo) >= gesamt * _CHROME_SHARE}


def outline_chunks(chunks: list[dict]) -> list[dict]:
    """The heading-like lines of a source as tiny chunks, its table of contents."""
    out: list[dict] = []
    chrome = _chrome_patterns(chunks)
    gesehen: set[str] = set()
    for c in chunks:
        for line in (c.get("content") or "").splitlines():
            line = line.strip()
            if not _is_heading_line(line):
                continue
            # The same line twice says nothing twice, and chrome only counts once.
            schluessel = _DIGITS.sub("#", line) if line in chrome or _DIGITS.sub("#", line) in chrome else line
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            out.append({"page_number": c.get("page_number"),
                        "start_time": c.get("start_time"), "content": line})
    return out


def _cut_to(chunks: list[dict], budget: int) -> list[dict]:
    """As many chunks from the front as the budget carries, at least one."""
    out: list[dict] = []
    used = 0
    for c in chunks:
        if out and used + _len(c) > budget:
            break
        out.append(c)
        used += _len(c)
    return out


def fill_sources_with_outline(
    sources: list[tuple[int, str, list[dict]]], budget: int | None = None,
) -> list[tuple[int, str, list[dict]]]:
    """Every source contributes its outline, the rest of the budget goes into depth."""
    budget = budget or tool_context_budget()
    with_content = [(sid, label, chunks) for sid, label, chunks in sources if chunks]
    if not with_content:
        return []

    # The base of every source: its outline, or its beginning when it has no headings.
    je_quelle = max(1000, budget // (2 * len(with_content)))
    base: dict[int, list[dict]] = {}
    left = budget
    for source_id, _label, chunks in with_content:
        gerippe = _cut_to(outline_chunks(chunks) or chunks, je_quelle)
        base[source_id] = gerippe
        left -= sum(_len(c) for c in gerippe)

    # What is left goes into depth, source by source from the front.
    taken: dict[int, list[dict]] = {}
    for source_id, _label, chunks in with_content:
        depth: list[dict] = []
        if left > 0:
            depth = _cut_to(chunks, left)
            left -= sum(_len(c) for c in depth)
        # A source that is in completely needs no base next to it.
        if len(depth) == len(chunks):
            taken[source_id] = depth
            continue
        # A base taken from the chunks themselves must not travel twice.
        schon = {id(c) for c in depth}
        rest = [c for c in base[source_id] if id(c) not in schon]
        # Back into document order, the outline has no place there and stays in front.
        stelle = {id(c): i for i, c in enumerate(chunks)}
        taken[source_id] = sorted(rest + depth, key=lambda c: stelle.get(id(c), -1))
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


