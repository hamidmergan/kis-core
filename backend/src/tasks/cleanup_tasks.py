"""Regelmaessiges Aufraeumen: abgelaufene Auftragsdateien.

Lag vorher als Endlosschleife (``_periodic_cleanup``) im Web-Prozess, gestartet
beim Hochfahren von kis-backend. Mit mehreren uvicorn-Prozessen haette JEDER
Prozess seine eigene Schleife gefahren, also dreifaches Loeschen zur selben
Stunde. Die Loeschvorgaenge sind zwar idempotent, aber es ist unnoetige Last und
das Logbuch wird unleserlich.

kis-celery-beat laeuft per Bauart genau einmal. Dort gehoert so eine Aufgabe hin.

Zeitplaneintraege werden hier NICHT mehr angefasst. Sie bleiben dauerhaft
erhalten, auch vergangene. Es gibt keine Aufbewahrungsdauer und keine
Einstellung dafuer.
"""

from loguru import logger

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


@celery_app.task(name="cleanup.exercise_progress", queue="general")
def run_cleanup_exercise_progress() -> int:
    """Uebungsantworten von vor dem Kalenderfeld aufraeumen. Naechtlich.

    Die Statistik zeigt nur die letzten sechs Monate, aeltere Antworten sind nicht
    erreichbar. Je Karte bleibt die juengste stehen, sonst faellt der Ring auf der
    Uebungskarte auf null, sobald ein Satz ein halbes Jahr geruht hat.
    """
    from src.features.ai_assistant.repository.exercises import prune_old_exercise_progress

    try:
        deleted = prune_old_exercise_progress()
        if deleted:
            logger.info("Cleanup: {} alte Uebungsantwort(en) geloescht", deleted)
        return deleted
    except Exception as e:
        logger.warning("Cleanup Uebungsantworten fehlgeschlagen: {}", e)
        return 0
