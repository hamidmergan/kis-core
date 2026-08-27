"""Drops exercises this course room already has, by exact comparison after generation."""

from src.services.aia_grammar_check import normalize


def item_key(front: str) -> str:
    """Comparison form of an exercise: its front, normalised. Empty when unusable."""
    return normalize(front or "")


def drop_repeats(items: list[dict], existing: list[str]) -> tuple[list[dict], int]:
    """Returns the new exercises and the number of discarded ones."""
    seen = {key for key in (item_key(f) for f in existing) if key}
    kept: list[dict] = []
    dropped = 0
    for item in items:
        key = item_key(item.get("front", ""))
        if not key:
            kept.append(item)
            continue
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        kept.append(item)
    return kept, dropped


def seen_by_user(user_id: int | None, tool: str) -> list[str]:
    """The fronts this person already had in this tool."""
    if not user_id:
        return []
    from src import database as db
    try:
        return db.seen_fingerprints(user_id, tool)
    except Exception:  # noqa: BLE001
        return []


__all__ = ["item_key", "drop_repeats", "seen_by_user"]
