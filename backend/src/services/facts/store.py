"""Where a run's facts live between attempts: the protocol, the job folder, the heartbeat."""

import asyncio
import contextlib
import json
from contextlib import asynccontextmanager
from typing import Callable, Protocol

from loguru import logger

from src import database as db
from src.storage import get_job_file, job_file_exists, save_job_file

FACTS_FILE = "facts.json"


class FactStore(Protocol):
    """Everything of one map phase that outlives a single attempt."""

    def load_extractions(self) -> dict[str, list[dict]]: ...
    def save_extraction(self, source_id: str, facts: list[dict]) -> None: ...
    def progress(self, step: str, part: int | None = None, total: int | None = None) -> None: ...
    def heartbeat(self) -> None: ...


def read_job_text(user_id: int, job_uuid: str, name: str) -> str | None:
    """A text file of the job folder, None when it is missing or unreadable."""
    if not job_file_exists(user_id, job_uuid, name):
        return None
    try:
        return get_job_file(user_id, job_uuid, name).decode("utf-8")
    except Exception as e:  # noqa: BLE001 - an unreadable piece is simply redone
        logger.warning("Auftrag {}: {} nicht lesbar ({})", job_uuid[:8], name, e)
        return None


def write_job_text(user_id: int, job_uuid: str, name: str, text: str) -> None:
    """One text file into the job folder, the counterpart of read_job_text."""
    save_job_file(user_id, job_uuid, name, text.encode("utf-8"))


def parse_job_json(job_uuid: str, name: str, raw: str | None, default):
    """Same fallback as an unreadable file: a broken one is treated as absent."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Auftrag {}: {} beschaedigt ({})", job_uuid[:8], name, e)
        return default


class JobFactStore:
    """The job folder as the map phase sees it, plus the progress row counted in sources.

    The guard is handed in rather than looked up, so this knows nothing about stages.
    """

    def __init__(self, user_id: int, job_uuid: str, source_ids: list[str],
                 guard: Callable[[], None] | None = None) -> None:
        self._user = user_id
        self._job = job_uuid
        self._ids = list(source_ids)
        self._guard_hook = guard
        self._facts: dict[str, list[dict]] = {}

    def _guard(self) -> None:
        """Asked before every write, so a run that lost its claim stops writing."""
        if self._guard_hook is not None:
            self._guard_hook()

    def load_extractions(self) -> dict[str, list[dict]]:
        roh = read_job_text(self._user, self._job, FACTS_FILE)
        self._facts = parse_job_json(self._job, FACTS_FILE, roh, {})
        return dict(self._facts)

    def save_extraction(self, source_id: str, facts: list[dict]) -> None:
        self._guard()
        self._facts[source_id] = facts
        write_job_text(self._user, self._job, FACTS_FILE,
                       json.dumps(self._facts, ensure_ascii=False))
        self.progress("map")

    def _sources_done(self) -> int:
        """Uploaded sources that have been read."""
        return sum(1 for sid in self._ids if sid in self._facts)

    def heartbeat(self) -> None:
        self._guard()
        db.touch_job_heartbeat(self._job)

    def progress(self, step: str, part: int | None = None, total: int | None = None) -> None:
        self._guard()
        # The map phase counts units, the person is shown the sources they picked.
        if step == "map":
            part, total = self._sources_done(), len(self._ids)
        fortschritt: dict = {"step": step}
        if part is not None and total is not None:
            fortschritt |= {"part": part, "total": total}
        db.update_job_status(self._job, "running", progress=fortschritt)
        db.touch_job_heartbeat(self._job)


async def _beat(store: FactStore, interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(store.heartbeat)
        except Exception:  # noqa: BLE001 - a missed beat must not sink the run
            return


@asynccontextmanager
async def keepalive(store: FactStore, interval: float):
    """Reports the job in while a call is out, a whole phase can pass in silence."""
    puls = asyncio.create_task(_beat(store, interval))
    try:
        yield
    finally:
        puls.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await puls
