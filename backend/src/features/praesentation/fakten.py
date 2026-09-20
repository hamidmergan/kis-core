"""The deck's map phase: every source read into facts, the numbered pool as material.

The pool is what the outline points at and what a slide is written from, so it is handed
on as facts and not as one block of text. Turning it into text is the caller's business.
"""

from dataclasses import asdict

from loguru import logger

from src.features.praesentation import lesen
from src.limits import (
    PRAESENTATION_FACTS_MAX_CHARS,
    PRAESENTATION_FACTS_MIN_CHARS,
    PRAESENTATION_HEARTBEAT_SECONDS,
    PRAESENTATION_MAP_CONCURRENCY,
    PRAESENTATION_MAX_BACKOFF_SECONDS,
    PRAESENTATION_PROMPT_RESERVE_CHARS,
    PRAESENTATION_READ_MAX_ATTEMPTS,
    PRAESENTATION_READ_MAX_FACTS,
    PRAESENTATION_RETRY_DELAY_SECONDS,
)
from src.services.facts import Fact, FactStore, Pacing, keepalive, map_sources
from src.services.facts import pool as fc

_POOL_FELDER = ("fact_id", "category", "fact", "citation", "source_id", "source_name",
                "reference")


def material_budget() -> int:
    """Characters of facts a single call may carry, from the admin's tool budget."""
    from src.features.ai_assistant.tasks._context_budget import tool_context_budget

    return max(20_000, tool_context_budget() - PRAESENTATION_PROMPT_RESERVE_CHARS)


def facts_per_source(sources: int) -> int:
    """Each source's share of the budget, so all of them together always fit.

    This is the whole point of the map phase: the share follows the number of sources,
    not the place a source happens to have in the list.
    """
    anteil = material_budget() // max(1, sources)
    return max(PRAESENTATION_FACTS_MIN_CHARS, min(PRAESENTATION_FACTS_MAX_CHARS, anteil))


def read_max_facts(sources: int) -> int:
    """Facts one read call may return, from that source's share of the budget."""
    aus_budget = facts_per_source(sources) // lesen.CHARS_PER_FACT
    return max(5, min(PRAESENTATION_READ_MAX_FACTS, aus_budget))


def pacing() -> Pacing:
    """How hard the read phase leans on the provider."""
    return Pacing(concurrency=PRAESENTATION_MAP_CONCURRENCY,
                  max_attempts=PRAESENTATION_READ_MAX_ATTEMPTS,
                  retry_delay=PRAESENTATION_RETRY_DELAY_SECONDS,
                  max_backoff=PRAESENTATION_MAX_BACKOFF_SECONDS)


async def build_pool(client, model: str, *, sources: list[dict], language: str,
                     store: FactStore, should_stop=None, book=None) -> list[Fact]:
    """Every source read once, the numbered pool of everything they gave up.

    Empty when not a single source gave up a fact, the caller then takes an older way.
    """
    anteil = facts_per_source(len(sources))
    deckel = read_max_facts(len(sources))
    raster = lesen.categories(language)

    async def _lesen(quelle: dict) -> list[dict] | None:
        return await lesen.read_source(client, model, source=quelle, language=language,
                                       grid=raster, max_chars=anteil, max_facts=deckel,
                                       book=book)

    async with keepalive(store, PRAESENTATION_HEARTBEAT_SECONDS):
        gelesen = await map_sources(sources, read=_lesen, store=store, pacing=pacing(),
                                    should_stop=should_stop)
    vorrat = fc.build_pool(sources, gelesen)
    if not vorrat:
        logger.warning("Präsentation: aus keiner Quelle liessen sich Fakten ziehen")
        return []
    logger.info("Präsentation: {} Fakten aus {} von {} Quellen",
                len(vorrat), len(fc.source_names(vorrat)), len(sources))
    return vorrat


def pool_als_liste(pool: list[Fact]) -> list[dict]:
    """The pool as plain data, that is what goes into the job folder."""
    return [asdict(f) for f in pool]


def pool_aus_liste(daten) -> list[Fact]:
    """The pool back out of the job folder, a damaged entry drops out instead of failing."""
    vorrat: list[Fact] = []
    for eintrag in daten or []:
        if not isinstance(eintrag, dict):
            continue
        try:
            vorrat.append(Fact(**{f: eintrag[f] for f in _POOL_FELDER if f in eintrag}))
        except TypeError:
            logger.warning("Präsentation: unvollstaendiger Fakt im Vorrat, er faellt weg")
    return vorrat
