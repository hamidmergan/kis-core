"""Dispatcher engine: ties the fair-share policy and area weighting together.

Two pure pieces, no IO:

- ``plan_dispatch`` -- given each lane's queued jobs, running jobs and its own
  concurrency cap, returns which job ids to start now per lane. Lanes are fully
  independent (hard isolation: ingest can never eat studio's slots and vice
  versa). Within a lane, per-user fair-share applies (``select_next_dispatches``).

- ``WeightedAreaSelector`` -- work-conserving weighted picker that distributes a
  shared budget (the rate-gate tokens) across areas by weight. An idle area is
  skipped so its share is lent to others, while a busy area never starves
  because every area with weight > 0 keeps getting turns.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Optional


class WeightedAreaSelector:
    """Deficit-weighted, work-conserving picker over areas sharing a budget.

    Each granted unit goes to the area with the lowest ``granted / weight`` ratio
    among areas that still have demand. Over many picks the grants converge to the
    weight ratios, but only areas that actually have work are ever served.
    """

    def __init__(self, weights: dict[str, float]) -> None:
        self.weights = dict(weights)
        self.granted: dict[str, float] = {a: 0.0 for a in weights}

    def pick(self, demand: dict[str, int]) -> Optional[str]:
        candidates = [
            a
            for a, d in demand.items()
            if d > 0 and self.weights.get(a, 0.0) > 0.0
        ]
        if not candidates:
            return None
        best = min(candidates, key=lambda a: (self.granted[a] / self.weights[a], a))
        self.granted[best] += 1.0
        return best


@dataclass(frozen=True)
class PoolJob:
    job_id: str
    user_id: int
    area: str
    created_at: float


def select_shared_pool(
    queued: list[PoolJob],
    running: list[tuple[int, str]],
    total_slots: int,
    weights: dict[str, float],
    area_granted: Optional[dict[str, float]] = None,
) -> list[str]:
    """Fill a single shared pool of ``total_slots`` background slots.

    Each free slot goes to an area by weighted deficit, then to the least-loaded
    user in that area, oldest job first. ``area_granted`` is a CUMULATIVE per-area
    grant tally that persists across dispatches (so studio at weight 2 really gets
    ~2x ingest's slots over time); it is updated in place. Pass ``None`` for a
    one-shot pick with no memory. ``total_slots <= 0`` means unlimited (own-GPU
    future): everything dispatches immediately, oldest first.
    """
    if total_slots <= 0:
        return [j.job_id for j in sorted(queued, key=lambda j: j.created_at)]

    free = total_slots - len(running)
    if free <= 0 or not queued:
        return []

    sel = WeightedAreaSelector(weights)
    if area_granted:
        for a, g in area_granted.items():
            if a in sel.granted:
                sel.granted[a] = g
    user_load: Counter = Counter(uid for uid, _area in running)

    remaining = sorted(queued, key=lambda j: j.created_at)
    chosen: list[str] = []
    while free > 0 and remaining:
        demand: dict[str, int] = {}
        for j in remaining:
            if weights.get(j.area, 0.0) > 0.0:
                demand[j.area] = demand.get(j.area, 0) + 1
        area = sel.pick(demand)
        if area is None:
            break
        cands = [j for j in remaining if j.area == area]
        best = min(cands, key=lambda j: (user_load[j.user_id], j.created_at))
        chosen.append(best.job_id)
        user_load[best.user_id] += 1
        remaining.remove(best)
        free -= 1
    if area_granted is not None:
        area_granted.clear()
        area_granted.update(sel.granted)
    return chosen
