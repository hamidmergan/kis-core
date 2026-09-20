"""Map phase: one call per source, a few at a time, and what survives a refusal."""

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from loguru import logger

from src.services.facts.store import FactStore


class RunInterrupted(Exception):
    """The stage ran out of working time, what is done is saved, the rest follows."""


class RateLimited(Exception):
    """The provider turned the call away or let it run out, the run slows down."""


def overloaded(exc: Exception) -> bool:
    """Whether this failure means too much at once rather than a bad request."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (429, 503):
        return True
    if isinstance(exc, asyncio.TimeoutError):
        return True
    return "timeout" in type(exc).__name__.casefold()


# One source in, its facts out, None once the reader has given up on it. A reader that
# wants to be paced rather than dropped raises RateLimited.
ReadSource = Callable[[dict], Awaitable[list[dict] | None]]


@dataclass(frozen=True)
class Pacing:
    """How hard the map phase leans on the provider, every number owned by the caller."""

    concurrency: int = 3
    max_attempts: int = 3
    retry_delay: float = 3.0
    max_backoff: float = 60.0


def _name(source: dict) -> str:
    """What a log line calls this source."""
    return source.get("filename") or source.get("source_id") or "?"


async def _read_one(read: ReadSource, source: dict, pacing: Pacing) -> list[dict] | None:
    """One source, retried with a growing wait for as long as the provider turns it away."""
    for versuch in range(pacing.max_attempts):
        try:
            return await read(source)
        except RateLimited as e:
            if versuch + 1 >= pacing.max_attempts:
                logger.warning("Fakten: Quelle '{}' bleibt abgewiesen ({})", _name(source), e)
                return None
            warte = min(pacing.retry_delay * 2 ** versuch, pacing.max_backoff)
            await asyncio.sleep(warte)
    return None


async def map_sources(sources: list[dict], *, read: ReadSource, store: FactStore,
                      pacing: Pacing,
                      should_stop: Callable[[], bool] | None = None) -> dict[str, list[dict]]:
    """Every source read once, as many at a time as the caller allows.

    What one source finished is written down before the next one starts, so a stage that
    runs out of time never costs a read that already succeeded. A source already in the
    store is not read again, that is what carries a run over a restart.
    """
    facts = dict(await asyncio.to_thread(store.load_extractions))
    await asyncio.to_thread(store.progress, "map")
    fehlend = [q for q in sources if q["source_id"] not in facts]
    if not fehlend:
        return facts
    semaphore = asyncio.Semaphore(max(1, pacing.concurrency))
    abgebrochen = False

    async def _eine(quelle: dict) -> None:
        nonlocal abgebrochen
        async with semaphore:
            # Asked after the semaphore, a check before it would pass for every coroutine at once.
            if should_stop and should_stop():
                abgebrochen = True
                return
            gelesen = await _read_one(read, quelle, pacing)
        # Written outside the semaphore, so the next source starts while this one saves.
        if gelesen:
            # A failure is never written down, the next round asks again.
            await asyncio.to_thread(store.save_extraction, quelle["source_id"], gelesen)
            facts[quelle["source_id"]] = gelesen

    await asyncio.gather(*(_eine(q) for q in fehlend))
    if abgebrochen:
        raise RunInterrupted
    return facts
