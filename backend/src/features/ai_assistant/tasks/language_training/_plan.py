"""The exercise plan of a set: which kind how often, and what is still missing."""


def plan_sentence(plan: list[str]) -> str:
    """The plan as numbers for the prompt, counted instead of described."""
    return ", ".join(f'{n} of kind "{kind}"' for kind, n in _counted(plan).items())


def room_left(plan: list[str], have: list[dict]) -> dict:
    """How many exercises per kind still fit the plan."""
    want = _counted(plan)
    for item in have:
        kind = item.get("_kind")
        if kind in want:
            want[kind] -= 1
    return {kind: max(0, n) for kind, n in want.items()}


def still_missing(plan: list[str], have: list[dict]) -> list[str]:
    """Which kinds are still missing, as a plan for the next attempt."""
    room = room_left(plan, have)
    out: list[str] = []
    for kind in _counted(plan):
        out.extend([kind] * room.get(kind, 0))
    return out


def _counted(plan: list[str]) -> dict:
    """The plan as a count, in the order of first appearance."""
    counts: dict[str, int] = {}
    for kind in plan:
        counts[kind] = counts.get(kind, 0) + 1
    return counts
