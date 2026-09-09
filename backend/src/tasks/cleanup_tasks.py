"""Regelmaessiges Aufraeumen abgelaufener Auftragsdateien, per celery-beat."""

from loguru import logger

from src.celery_app import celery_app
from src.features.access_codes import repository as repo
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


@celery_app.task(name="cleanup.job_cap", queue="general")
def run_cleanup_job_cap() -> int:
    """Trims every user hourly down to the pool set in the admin area."""
    from src.database import get_users_over_cap
    from src.storage import evict_jobs_over_cap

    entfernt = 0
    try:
        for user_id in get_users_over_cap():
            entfernt += evict_jobs_over_cap(user_id)
        if entfernt:
            logger.info("Cleanup: {} Auftrag/Auftraege ueber dem Vorrat geloescht", entfernt)
        return entfernt
    except Exception as e:
        logger.warning("Cleanup Auftrags-Vorrat fehlgeschlagen: {}", e)
        return entfernt


@celery_app.task(name="cleanup.exercise_progress", queue="general")
def run_cleanup_exercise_progress() -> int:
    """Nightly clears exercise answers older than the calendar view reaches."""
    from src.features.ai_assistant.repository.exercises import prune_old_exercise_progress

    try:
        deleted = prune_old_exercise_progress()
        if deleted:
            logger.info("Cleanup: {} alte Uebungsantwort(en) geloescht", deleted)
        return deleted
    except Exception as e:
        logger.warning("Cleanup Uebungsantworten fehlgeschlagen: {}", e)
        return 0


@celery_app.task(name="cleanup.lock_expired_access_accounts", queue="general")
def run_lock_expired_access_accounts() -> int:
    """Locks (never deletes) accounts whose access-code deadline has passed. Hourly."""
    try:
        gesperrt = repo.lock_expired_accounts()
        if gesperrt:
            logger.info("Cleanup: {} Testkonto/Testkonten wegen Ablauf gesperrt", gesperrt)
        return gesperrt
    except Exception as e:
        logger.warning("Cleanup Testkonten-Sperrung fehlgeschlagen: {}", e)
        return 0


@celery_app.task(name="cleanup.speech_cache", queue="general")
def run_cleanup_speech_cache() -> int:
    """Nightly clears spoken sentences nobody has listened to in a long time."""
    from src.features.ai_assistant.repository.speech_cache import prune

    try:
        deleted = prune()
        if deleted:
            logger.info("Cleanup: {} gesprochene(r) Beispielsatz/-saetze geloescht", deleted)
        return deleted
    except Exception as e:
        logger.warning("Cleanup Aussprache-Vorrat fehlgeschlagen: {}", e)
        return 0
