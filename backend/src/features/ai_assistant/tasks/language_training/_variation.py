"""The name of a generated set, decided inside the generation call.

The set TITLE, and only the title. The context sweep in ``_context_budget`` gives each run
different material and ``_dedup`` drops any exercise that repeats an earlier one, but
neither touches the name of the set: left alone the model names the document instead of
the set and several sets end up sharing one title. Both correctives therefore ride along
in the generation prompt, the naming rule and the names already taken, so a finished set
costs no title call of its own.

Only titles, deliberately. Listing the earlier ITEMS was tried and reverted: fed back into
the prompt they act as few-shot material and the model copies them verbatim (see the
comments in the generators). A title is a single short string with no such pull. That
same finding is why ``_dedup`` filters after generation instead of warning beforehand.

Language-agnostic by construction: nothing here inspects words, it only passes back text
the model itself produced earlier.
"""

# Live in tasks/_titles.py, re-exported here because the set title is this module's job.
from src.features.ai_assistant.tasks._titles import (  # noqa: F401
    is_title_taken,
    next_free_counter,
)

# The block sits in front of an already large context, so it stays a footnote.
_MAX_TITLES = 10
_MAX_LEN = 90

# Names the set, not the document. Without this the full context pulls the model
# towards the filename or the law, which is what the old separate title call fixed.
_NAMING_RULE = (
    "\n\nTITLE OF THIS SET: name what THESE exercises are about, the concrete matter they "
    "have in common, for example the procedure, the rule, the step or the material. NEVER "
    "the document, the law, the lecture, the course or the field as a whole, and never a "
    "filename. Max 6 words, no quotation marks."
)


def title_avoidance_block(titles: list[str]) -> str:
    """Prompt block for the set title, with the names already taken appended."""
    seen: set[str] = set()
    picked: list[str] = []
    for raw in titles:
        text = " ".join((raw or "").split())[:_MAX_LEN]
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        picked.append(text)
        if len(picked) >= _MAX_TITLES:
            break
    if not picked:
        return _NAMING_RULE
    return (
        _NAMING_RULE
        + "\n\nTITLES ALREADY IN USE in this workspace:\n"
        + "\n".join(f"  - {t}" for t in picked)
        + "\nThe new title MUST differ from every one of them. Name what THIS set is "
        "actually about, taken from the exercises you just wrote, not the document as a "
        "whole. Never reuse a title from the list above."
    )


def build_title_avoidance_block(workspace_id: int | None, tool: str) -> str:
    """The block for this course room and tool, from the finished sets."""
    if not workspace_id:
        return _NAMING_RULE
    from src import database as db
    try:
        return title_avoidance_block(db.get_recent_exercise_titles(workspace_id, tool))
    except Exception:  # noqa: BLE001
        return _NAMING_RULE


def resolve_set_title(workspace_id: int | None, tool: str, title: str) -> str:
    """The name a finished set gets, numbered when the model reused one."""
    title = (title or "").strip()
    if not title or not workspace_id:
        return title
    from src import database as db
    try:
        taken = db.get_recent_exercise_titles(workspace_id, tool, limit=100)
    except Exception:  # noqa: BLE001 - never fail a finished set over its name
        return title
    if not is_title_taken(title, taken):
        return title
    return next_free_counter(title, taken)


__all__ = [
    "title_avoidance_block",
    "build_title_avoidance_block",
    "resolve_set_title",
    "is_title_taken",
]
