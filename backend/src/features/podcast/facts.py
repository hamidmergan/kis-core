"""The podcast's map phase: every source read into facts, the numbered pool as material."""

from loguru import logger

from src.features.podcast import reading
from src.limits import (
    PODCAST_FACTS_MAX_CHARS,
    PODCAST_FACTS_MIN_CHARS,
    PODCAST_HEARTBEAT_SECONDS,
    PODCAST_MAP_CONCURRENCY,
    PODCAST_MAX_BACKOFF_SECONDS,
    PODCAST_PROMPT_RESERVE_CHARS,
    PODCAST_READ_MAX_ATTEMPTS,
    PODCAST_READ_MAX_FACTS,
    PODCAST_RETRY_DELAY_SECONDS,
)
from src.services.facts import FactStore, Pacing, keepalive, map_sources
from src.services.facts import pool as fc


def material_budget() -> int:
    """Characters of facts the script call may carry, from the admin's tool budget."""
    from src.features.ai_assistant.tasks._context_budget import tool_context_budget

    return max(20_000, tool_context_budget() - PODCAST_PROMPT_RESERVE_CHARS)


def facts_per_source(sources: int) -> int:
    """Each source's share of the budget, so all of them together always fit.

    This is the whole point of the map phase: the share follows the number of sources,
    not the place a source happens to have in the list.
    """
    anteil = material_budget() // max(1, sources)
    return max(PODCAST_FACTS_MIN_CHARS, min(PODCAST_FACTS_MAX_CHARS, anteil))


def read_max_facts(sources: int) -> int:
    """Facts one read call may return, from that source's share of the budget."""
    aus_budget = facts_per_source(sources) // reading.CHARS_PER_FACT
    return max(5, min(PODCAST_READ_MAX_FACTS, aus_budget))


def pacing() -> Pacing:
    """How hard the read phase leans on the provider."""
    return Pacing(concurrency=PODCAST_MAP_CONCURRENCY,
                  max_attempts=PODCAST_READ_MAX_ATTEMPTS,
                  retry_delay=PODCAST_RETRY_DELAY_SECONDS,
                  max_backoff=PODCAST_MAX_BACKOFF_SECONDS)


async def build_pool_text(client, model: str, *, sources: list[dict], language: str,
                          store: FactStore, should_stop=None, book=None) -> str:
    """Every source read once, the numbered pool as the material of the script call.

    Empty when not a single source gave up a fact, the caller then takes an older way.
    """
    anteil = facts_per_source(len(sources))
    deckel = read_max_facts(len(sources))
    raster = reading.categories(language)

    async def _lesen(quelle: dict) -> list[dict] | None:
        return await reading.read_source(client, model, source=quelle, language=language,
                                         grid=raster, max_chars=anteil, max_facts=deckel,
                                         book=book)

    async with keepalive(store, PODCAST_HEARTBEAT_SECONDS):
        gelesen = await map_sources(sources, read=_lesen, store=store, pacing=pacing(),
                                    should_stop=should_stop)
    vorrat = fc.build_pool(sources, gelesen)
    if not vorrat:
        logger.warning("Podcast: aus keiner Quelle liessen sich Fakten ziehen")
        return ""
    # Without the proofs: they anchor the reading call, the script call has no use for them.
    text = fc.pool_block(vorrat, material_budget())
    logger.info("Podcast: {} Fakten aus {} von {} Quellen, {} Zeichen",
                len(vorrat), len(fc.source_names(vorrat)), len(sources), len(text))
    return text
