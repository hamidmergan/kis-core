"""Dispatcher engine: fair-share scheduling for the shared background pool.

Two pure pieces, no IO:

- ``WeightedAreaSelector`` -- work-conserving weighted picker that distributes a
  shared budget (the rate-gate tokens) across areas by weight. An idle area is
  skipped so its share is lent to others, while a busy area never starves
  because every area with weight > 0 keeps getting turns.

- ``select_shared_pool`` -- fills a single shared pool of background slots: each
  free slot goes to an area by weighted deficit, then to the fairest user in
  that area (fewest running jobs, then fewest cumulative grants, then oldest).
  ``PoolJob`` is the queued-job record it consumes.
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
    user_granted: Optional[dict[int, int]] = None,
) -> list[str]:
    """Fill a single shared pool of ``total_slots`` background slots.

    Each free slot goes to an area by weighted deficit, then to the fairest user
    in that area. User fairness prefers (1) fewest jobs currently running, then
    (2) fewest CUMULATIVE grants (``user_granted``), then oldest job. The
    cumulative tally is what stops a flooder whose older jobs would otherwise win
    every created-at tiebreak; it persists across dispatches and is updated in
    place. ``area_granted`` does the same for areas. Pass ``None`` for a one-shot
    pick with no memory. ``total_slots <= 0`` means unlimited (own-GPU future):
    everything dispatches immediately, oldest first.
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
        ug = user_granted if user_granted is not None else {}
        best = min(cands, key=lambda j: (user_load[j.user_id], ug.get(j.user_id, 0), j.created_at))
        chosen.append(best.job_id)
        user_load[best.user_id] += 1
        if user_granted is not None:
            user_granted[best.user_id] = user_granted.get(best.user_id, 0) + 1
        remaining.remove(best)
        free -= 1
    if area_granted is not None:
        area_granted.clear()
        area_granted.update(sel.granted)
    return chosen
