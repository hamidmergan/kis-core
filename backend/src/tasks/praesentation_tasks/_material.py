"""The material of one deck: the facts of every source, or one of the older ways."""

import asyncio

from loguru import logger

from src.features.praesentation import fakten as fk
from src.features.praesentation import material as mat
from src.features.praesentation.schemas import PraesentationParams
from src.security.usage_log import log_llm_response
from src.services.facts import Fact, JobFactStore, RunInterrupted
from src.services.facts import pool as fc
from src.services.job_recovery import still_mine
from src.tasks._stage import StageClock, StageLost
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled


class PraesentationFactStore(JobFactStore):
    """The shared fact store, guarded by the run's cancel mark and the stage claim."""

    def __init__(self, user_id: int, job_uuid: str, source_ids: list[str],
                 versuch: int) -> None:
        self._versuch = versuch
        super().__init__(user_id, job_uuid, source_ids, guard=self._wanted_and_mine)

    def _wanted_and_mine(self) -> None:
        """A cancelled run and a handed over stage both stop writing right here."""
        assert_not_cancelled(self._job)
        if not still_mine(self._job, self._versuch):
            raise StageLost(self._job)


def _llm():
    """The chat route's client, the same one that plans the deck afterwards."""
    from src.services import feature_router

    return feature_router.make_llm_client(feature_router.resolve("chat"))


async def _build(user_id: int, job_uuid: str, material: dict, params: PraesentationParams,
                 clock: StageClock, versuch: int) -> tuple[list[Fact], str]:
    """The run's material: its numbered fact pool, or the snapshot an older way produced.

    Exactly one of the two carries content. The pool is what lets a slide be written from
    its own facts, the snapshot is what the deck falls back to when no fact could be read.
    """
    quellen = material.get("sources") or []
    vorrat: list[Fact] = []

    async def _fakten() -> str:
        """One read call per source. Whatever it cannot deliver falls to the older ways.

        Resolving the provider sits inside the guard too: a missing one is exactly the
        case the older ways exist for.
        """
        nonlocal vorrat
        try:
            llm = _llm()
            speicher = PraesentationFactStore(user_id, job_uuid,
                                              [q["source_id"] for q in quellen], versuch)
            vorrat = await fk.build_pool(
                llm._async_client, llm._model, sources=quellen, language=params.language,
                store=speicher, should_stop=clock.over,
                book=lambda antwort: log_llm_response("praesentation", llm, antwort))
        except (RunInterrupted, JobCancelled, StageLost):
            # The stage is over or the run is gone, both belong to the task, not here.
            raise
        except Exception as e:  # noqa: BLE001 - the deck still has three ways left
            logger.warning("Präsentation: Fakten fehlgeschlagen, es geht ohne sie weiter: {}", e)
            return ""
        # Only its length matters to the chain, the pool itself travels in the closure.
        return fc.pool_block(vorrat, fk.material_budget()) if vorrat else ""

    text = await mat.kontext(mat.als_chunks(quellen), params.instructions,
                             material.get("workspace_id"), material.get("source_uuids"),
                             _fakten)
    # The chain returns the facts unchanged when they won, so the pool alone decides.
    return (vorrat, "") if vorrat else ([], text)


def build(user_id: int, job_uuid: str, material: dict, params: PraesentationParams,
          clock: StageClock, versuch: int) -> tuple[list[Fact], str]:
    """Synchronous door into the material phase, for the Celery task calling in."""
    return asyncio.run(_build(user_id, job_uuid, material, params, clock, versuch))
