"""Pure per-lane fair-share dispatch policy for AIA worker jobs.

Decides which queued jobs to start now, given the lane's concurrency cap and
what is already running. Fairness rule: a free slot goes to the waiting user
with the fewest jobs currently counted against them (running + already chosen
in this pass), tie-broken by oldest queued. This yields round-robin across
users while letting a lone user use the whole cap. No DB, no Redis, no Celery.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class QueuedJob:
    job_id: str
    user_id: int
    created_at: float


def select_next_dispatches(
    queued: list[QueuedJob],
    running_user_ids: list[int],
    concurrency: int,
) -> list[str]:
    """Return the job ids to start now, never exceeding the free slot count."""
    free = concurrency - len(running_user_ids)
    if free <= 0 or not queued:
        return []

    load: dict[int, int] = {}
    for uid in running_user_ids:
        load[uid] = load.get(uid, 0) + 1

    remaining = sorted(queued, key=lambda j: j.created_at)
    chosen: list[str] = []
    while free > 0 and remaining:
        # least-loaded user wins; remaining is oldest-first so the min is a
        # stable oldest-within-lowest-load pick.
        best = min(remaining, key=lambda j: (load.get(j.user_id, 0), j.created_at))
        chosen.append(best.job_id)
        load[best.user_id] = load.get(best.user_id, 0) + 1
        remaining.remove(best)
        free -= 1
    return chosen
