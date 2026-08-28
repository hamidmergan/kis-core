"""Warms the evidence caches while the answer is still streaming."""

import asyncio

from src import database as db
from src.limits import AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS
from src.services.aia_embeddings import get_embedding_provider

from ._evidence import _ATTRIB_CANDIDATES, _AttributionPrewarmer


def start_prewarm(*, workspace_id: int, source_ids, seen_pages_by_source) -> tuple:
    """Starts the warm-up pump and returns prewarmer, task and its stop signal."""
    # Short timeout, no retry, the warm-up is only a shortcut.
    _pw_prov = get_embedding_provider(timeout=AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS,
                       retry_on_timeout=False)

    def _pw_search(_ln, _vec):
        try:
            return db.hybrid_search_chunks(
                workspace_id, _ln, _vec or _pw_prov.embed_one(_ln),
                source_ids=source_ids, limit=_ATTRIB_CANDIDATES,
                # Must be the same restriction as in _raw_search, otherwise the cache does not match.
                seen_pages=seen_pages_by_source)
        except Exception:
            return []

    prewarmer = _AttributionPrewarmer(_pw_prov.embed, _pw_search)
    pump_stop = asyncio.Event()

    async def _prewarm_pump():
        # The warm-up may cost a few calls per answer, not one per line.
        _PREWARM_POLL_SECONDS = 2.0
        _PREWARM_MAX_FLUSHES = 6
        while not pump_stop.is_set():
            try:
                await asyncio.wait_for(pump_stop.wait(), timeout=_PREWARM_POLL_SECONDS)
            except asyncio.TimeoutError:
                pass
            if pump_stop.is_set():
                break
            if prewarmer.flushes < _PREWARM_MAX_FLUSHES and prewarmer.pending_count():
                try:
                    await prewarmer.flush()
                except Exception:
                    pass
        await prewarmer.flush()  # final drain of whatever is still pending

    return prewarmer, asyncio.create_task(_prewarm_pump()), pump_stop
