"""Regelmaessiges Aufraeumen: abgelaufene Auftragsdateien und alte Zeitplaneintraege.

Lag vorher als Endlosschleife (``_periodic_cleanup``) im Web-Prozess, gestartet
beim Hochfahren von kis-backend. Mit mehreren uvicorn-Prozessen haette JEDER
Prozess seine eigene Schleife gefahren, also dreifaches Loeschen zur selben
Stunde. Die Loeschvorgaenge sind zwar idempotent, aber es ist unnoetige Last und
das Logbuch wird unleserlich.

kis-celery-beat laeuft per Bauart genau einmal. Dort gehoert so eine Aufgabe hin.
"""

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.storage import cleanup_expired_files


@celery_app.task(name="cleanup.expired_files", queue="general")
def run_cleanup_expired_files() -> int:
    """Abgelaufene Auftragsdateien loeschen. Stuendlich."""
    try:
        deleted = cleanup_expired_files()
        if deleted:
            logger.info("Cleanup: {} expired job(s) deleted", deleted)
        return deleted
    except Exception as e:
        logger.warning("Cleanup error: {}", e)
        return 0


@celery_app.task(name="cleanup.prune_schedule", queue="general")
def run_prune_schedule() -> int:
    """Vergangene Zeitplaneintraege ausduennen. Taeglich.

    Die Aufbewahrungsdauer steht in der Einstellung
    ``aia_schedule_retention_days``. -1 ist der Standard und heisst: nie
    ausduennen, Eintraege bleiben fuer immer.
    """
    try:
        raw = db.get_setting("aia_schedule_retention_days", "-1")
        try:
            retention_days = int(raw)
        except ValueError:
            retention_days = -1
        if retention_days <= 0:
            return 0
        pruned = db.prune_old_entries(retention_days)
        if pruned:
            logger.info("Schedule cleanup: {} past entries pruned (>{}d)", pruned, retention_days)
        return pruned
    except Exception as e:
        logger.warning("Schedule cleanup error: {}", e)
        return 0
