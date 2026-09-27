"""Which Celery tasks the broker still holds, waiting in a queue or picked up and unacknowledged."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from loguru import logger

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")

# Every queue a worker listens on, see task_routes in celery_app.py.
QUEUES = ("general", "long", "tts", "screencast", "aia", "aia_ingest", "control")


def _lists(queue: str) -> list[str]:
    """Redis keeps one list per priority step, the default step under the queue's own name."""
    from kombu.transport.redis import PRIORITY_STEPS, Channel

    return [queue] + [f"{queue}{Channel.sep}{step}" for step in PRIORITY_STEPS if step]


# Kombu keeps picked up but unacknowledged messages here, with acks_late that includes running tasks.
_UNACKED_KEY = "unacked"


def _redis():
    import redis as _redis_lib
    return _redis_lib.from_url(_REDIS_URL, socket_connect_timeout=2, socket_timeout=5)


def _task_id(raw) -> str | None:
    try:
        return json.loads(raw)["headers"]["id"]
    except (ValueError, KeyError, TypeError):
        return None


@dataclass
class Snapshot:
    """Waiting means still in a queue, taken means picked up by a worker and not yet acknowledged."""

    waiting: set[str] = field(default_factory=set)
    taken: set[str] = field(default_factory=set)

    def holds(self, task_id: str | None) -> bool:
        return bool(task_id) and (task_id in self.waiting or task_id in self.taken)


def snapshot(r=None) -> Snapshot | None:
    """Every task the broker still holds, None when the broker cannot be read."""
    try:
        r = r if r is not None else _redis()
        stand = Snapshot()
        for queue in QUEUES:
            for key in _lists(queue):
                for raw in r.lrange(key, 0, -1):
                    task_id = _task_id(raw)
                    if task_id:
                        stand.waiting.add(task_id)
        for raw in r.hvals(_UNACKED_KEY):
            try:
                task_id = _task_id(json.dumps(json.loads(raw)[0]))
            except (ValueError, IndexError, TypeError):
                task_id = None
            if task_id:
                stand.taken.add(task_id)
        return stand
    except Exception as e:  # noqa: BLE001 - without an answer nobody may declare a job lost
        logger.warning("Broker nicht lesbar, kein Auftrag gilt als verloren: {}", e)
        return None
