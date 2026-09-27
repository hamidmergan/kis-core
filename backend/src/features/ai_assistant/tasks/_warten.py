"""Puts a Francis job back in line when only the provider was too slow or too busy."""

import random
import time

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from src.limits import PROVIDER_BUSY_MAX_HOURS, PROVIDER_BUSY_WAIT_SECONDS
from src.services.upstream_errors import is_upstream_busy

# A job that hits the time limit this often is too big and not merely waiting.
ZEITGRENZE_ANLAEUFE = 3


def platz_nachfuehren(kwargs: dict, ergebnis) -> None:
    """Gives the Francis slot the new task id, otherwise the reaper takes the waiting run for lost and starts it twice."""
    platz, neue_id = kwargs.get("_aia_job_uuid"), getattr(ergebnis, "id", None)
    if not (platz and neue_id):
        return
    try:
        from src.features.ai_assistant.repository.jobs import DbJobStore
        DbJobStore().set_celery_task_id(platz, neue_id)
    except Exception as fehler:  # noqa: BLE001 - the run still waits, at worst the reaper starts it once more
        logger.error("KI Tutor: Platz {} behält die alte Auftragsnummer: {}", platz, fehler)


def wieder_einreihen(task, e: Exception, *, anlauf: int, seit: float | None, args: list, kwargs: dict) -> bool:
    """Requeues the same run after a short wait, the caller then keeps its seat and marks nothing failed."""
    if isinstance(e, SoftTimeLimitExceeded):
        if anlauf >= ZEITGRENZE_ANLAEUFE:
            return False
    elif not is_upstream_busy(e):
        return False
    seit = seit or time.time()
    if time.time() - seit > PROVIDER_BUSY_MAX_HOURS * 3600:
        return False
    warte = random.uniform(*PROVIDER_BUSY_WAIT_SECONDS)
    try:
        ergebnis = task.apply_async(args=args, kwargs={**kwargs, "anlauf": anlauf + 1, "seit": seit}, countdown=warte)
    except Exception as fehler:  # noqa: BLE001 - without a broker the job fails as before
        logger.error("KI Tutor: {} konnte nicht neu eingereiht werden: {}", task.name, fehler)
        return False
    platz_nachfuehren(kwargs, ergebnis)
    logger.warning("KI Tutor: {} wartet {:.0f} s auf den Anbieter ({}), Lauf {}",
                   task.name, warte, type(e).__name__, anlauf + 2)
    return True
