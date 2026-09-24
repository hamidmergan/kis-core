"""Several model calls at once, and one at a time as soon as the provider struggles.

Nothing is remembered beyond one run: the next run starts at the full number again.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from openai import APIConnectionError

from src.services.openai_compat_llm.base import is_transient_error

# Marks a job that was never started because the run has to stop.
SKIPPED = object()

# One failure of a job is tried again alone, a second one ends the run.
_ATTEMPTS = 2


def overloaded(e: Exception) -> bool:
    """A timeout, a refused connection, a 429 or a 5xx: the provider, not the request."""
    return isinstance(e, (APIConnectionError, TimeoutError)) or is_transient_error(e)


async def run_limited(jobs: list[Callable[[], Awaitable[Any]]], at_once: int, *,
                      may_start: Callable[[], bool] | None = None) -> list[Any]:
    """Every job, at most ``at_once`` running, results in the order of the jobs."""
    zustand = {"grenze": max(1, at_once), "laufend": 0}
    wechsel = asyncio.Condition()

    async def platz() -> None:
        async with wechsel:
            await wechsel.wait_for(lambda: zustand["laufend"] < zustand["grenze"])
            zustand["laufend"] += 1

    async def frei() -> None:
        async with wechsel:
            zustand["laufend"] -= 1
            wechsel.notify_all()

    async def eine(job: Callable[[], Awaitable[Any]]) -> Any:
        for versuch in range(1, _ATTEMPTS + 1):
            await platz()
            try:
                if may_start is not None and not may_start():
                    return SKIPPED
                return await job()
            except Exception as e:
                if not overloaded(e) or versuch >= _ATTEMPTS:
                    raise
                if zustand["grenze"] > 1:
                    logger.warning("Anbieter ueberlastet ({}), ab jetzt ein Aufruf nach dem anderen", e)
                zustand["grenze"] = 1
            finally:
                await frei()
        raise RuntimeError("unreachable")

    return list(await asyncio.gather(*(eine(j) for j in jobs)))
