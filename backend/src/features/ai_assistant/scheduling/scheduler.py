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

from dataclasses import dataclass
from typing import Optional

from .fair_dispatch import QueuedJob, select_next_dispatches


@dataclass
class AreaState:
    name: str
    concurrency: int
    queued: list[QueuedJob]
    running_user_ids: list[int]


def plan_dispatch(areas: list[AreaState]) -> dict[str, list[str]]:
    """Per area, choose the job ids to start now. Areas are isolated."""
    return {
        area.name: select_next_dispatches(
            area.queued, area.running_user_ids, area.concurrency
        )
        for area in areas
    }


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
