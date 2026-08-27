"""Keeps generated sets from getting the same title, via the title alone."""

# Lives in tasks/_titles.py, only re-exported here for the test.
from src.features.ai_assistant.tasks._titles import is_title_taken  # noqa: F401

# The block sits in front of an already large context, so it stays a footnote.
_MAX_TITLES = 10
_MAX_LEN = 90


def title_avoidance_block(titles: list[str]) -> str:
    """Prompt block with the titles already taken, empty when there are none."""
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
    """The block for this course room and tool, from the finished sets."""
    if not workspace_id:
        return ""
    from src import database as db
    try:
        return title_avoidance_block(db.get_recent_exercise_titles(workspace_id, tool))
    except Exception:  # noqa: BLE001
        return ""


def resolve_set_title(client, model, workspace_id: int | None, tool: str,
                      fallback: str, items: list[dict]) -> str:
    """The name a finished set gets."""
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
