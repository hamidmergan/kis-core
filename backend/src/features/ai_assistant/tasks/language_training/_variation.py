"""Keeps generated sets from repeating themselves.

The set TITLE, and only the title. The context sweep in ``_context_budget`` gives each run
different material and ``_dedup`` drops any exercise that repeats an earlier one, but
neither touches the name of the set: the model never learns that a set already exists, so
it names the document instead of the set and several sets end up sharing one title.

Only titles, deliberately. Listing the earlier ITEMS was tried and reverted: fed back into
the prompt they act as few-shot material and the model copies them verbatim (see the
comments in the generators). A title is a single short string with no such pull. That
same finding is why ``_dedup`` filters after generation instead of warning beforehand.

Language-agnostic by construction: nothing here inspects words, it only passes back text
the model itself produced earlier.
"""

# Liegt seit dem Umzug in ``tasks/_titles.py``, weil Mindmap und Datentabelle dieselbe
# Pruefung brauchen. Hier weiter importiert, damit die vorhandenen Aufrufer und der
# Test unveraendert von diesem Modul lesen koennen.
from src.features.ai_assistant.tasks._titles import is_title_taken  # noqa: F401

# The block sits in front of an already large context, so it stays a footnote.
_MAX_TITLES = 10
_MAX_LEN = 90


def title_avoidance_block(titles: list[str]) -> str:
    """Prompt block naming the titles already in use. Empty when there are none.

    Carries a leading blank line, so a caller can append it to a system prompt without
    checking whether it is empty.
    """
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
        return ""
    return (
        "\n\nTITLES ALREADY IN USE in this workspace:\n"
        + "\n".join(f"  - {t}" for t in picked)
        + "\nThe new title MUST differ from every one of them. Name what THIS set is "
        "actually about, taken from the exercises you just wrote, not the document as a "
        "whole. Never reuse a title from the list above."
    )


def build_title_avoidance_block(workspace_id: int | None, tool: str) -> str:
    """The block for this workspace+tool, read from the finished sets.

    A missing workspace (older queued tasks) or a failing query yields an empty block
    rather than an error: a duplicate title is a blemish, never a reason to fail a set.
    """
    if not workspace_id:
        return ""
    from src import database as db
    try:
        return title_avoidance_block(db.get_recent_exercise_titles(workspace_id, tool))
    except Exception:  # noqa: BLE001
        return ""


def resolve_set_title(client, model, workspace_id: int | None, tool: str,
                      fallback: str, items: list[dict]) -> str:
    """The name a finished set gets.

    Everything about the naming itself lives in ``tasks._titles``. What stays here is the
    one thing that is specific to exercise sets: which titles count as taken, namely the
    recent ready sets of this workspace and tool.
    """
    from src.features.ai_assistant.tasks._titles import resolve_title

    fallback = (fallback or "").strip()
    if not workspace_id or not items:
        return fallback
    from src import database as db
    try:
        taken = db.get_recent_exercise_titles(workspace_id, tool, limit=100)
    except Exception:  # noqa: BLE001 - never fail a finished set over its name
        return fallback

    return resolve_title(client, model, taken, fallback, [(it.get("front") or "") for it in items])


__all__ = [
    "title_avoidance_block",
    "build_title_avoidance_block",
    "resolve_set_title",
    "is_title_taken",
]
