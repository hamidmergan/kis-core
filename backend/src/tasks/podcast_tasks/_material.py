"""The material of one episode: the facts of every source, or one of the older ways."""

import asyncio

from loguru import logger

from src.features.podcast import facts as fk
from src.features.podcast import instruction, source_text
from src.features.podcast.schemas import PodcastParams
from src.security.usage_log import log_llm_response
from src.services.facts import JobFactStore, RunInterrupted
from src.services.job_recovery import still_mine
from src.tasks._stage import StageClock, StageLost
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled


class PodcastFactStore(JobFactStore):
    """The shared fact store, guarded by the podcast's cancel mark and the stage claim."""

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
    """The chat route's client, the same one that writes the script afterwards."""
    from src.services import feature_router

    return feature_router.make_llm_client(feature_router.resolve("chat"))


def as_chunks(sources: list[dict]) -> list[tuple[str, list[dict]]]:
    """The raw sources in the shape the older ways expect, one labelled pile of pieces each."""
    return [(q["filename"], source_text.to_pieces(q["content"])) for q in sources]


async def _build(user_id: int, job_uuid: str, material: dict, params: PodcastParams,
                 clock: StageClock, versuch: int, zahlen: dict) -> str:
    quellen = material.get("sources") or []

    async def _fakten() -> str:
        """One read call per source. Whatever it cannot deliver falls to the older ways.

        Resolving the provider sits inside the guard too: a missing one is exactly the
        case the older ways exist for.
        """
        try:
            llm = _llm()
            speicher = PodcastFactStore(user_id, job_uuid,
                                        [q["source_id"] for q in quellen], versuch)
            return await fk.build_pool_text(
                llm._async_client, llm._model, sources=quellen, language=params.language,
                store=speicher, should_stop=clock.over,
                book=lambda antwort: log_llm_response("podcast", llm, antwort))
        except (RunInterrupted, JobCancelled, StageLost):
            # The stage is over or the run is gone, both belong to the task, not here.
            raise
        except Exception as e:  # noqa: BLE001 - the episode still has three ways left
            logger.warning("Podcast: Fakten fehlgeschlagen, es geht ohne sie weiter: {}", e)
            return ""

    return await instruction.build_context(
        as_chunks(quellen), params.instructions, material.get("workspace_id"),
        material.get("source_uuids"), zahlen, facts=_fakten)


def build(user_id: int, job_uuid: str, material: dict, params: PodcastParams,
          clock: StageClock, versuch: int, zahlen: dict) -> str:
    """Synchronous door into the material phase, for the Celery task calling in."""
    return asyncio.run(_build(user_id, job_uuid, material, params, clock, versuch, zahlen))
