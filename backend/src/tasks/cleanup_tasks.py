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


@celery_app.task(name="cleanup.job_cap", queue="general")
def run_cleanup_job_cap() -> int:
    """Jeden Nutzer auf die letzten MAX_RESULT_FILES Auftraege zurechtstutzen. Stuendlich.

    Normalerweise raeumt schon das Speichern eines Ergebnisses mit. Wer nur
    Fehlversuche produziert, loest das aber nie aus, und seit die Frist von sieben
    Tagen weg ist, holt sie auch niemand mehr ab. Dafuer ist dieser Durchlauf da.
    """
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


@celery_app.task(name="cleanup.speech_cache", queue="general")
def run_cleanup_speech_cache() -> int:
    """Gesprochene Beispielsaetze aufraeumen, die lange niemand gehoert hat. Naechtlich.

    Der Vorrat waechst nur durch Nutzung, wird aber nie von selbst kleiner: eine
    geloeschte Quelle nimmt ihre Toene nicht mit, weil der Schluessel am Satz haengt
    und nicht an der Karte. Wer einen aufgeraeumten Satz doch wieder braucht, wartet
    einmal fuenf Sekunden und hat ihn zurueck.
    """
    from src.features.ai_assistant.repository.speech_cache import prune

    try:
        deleted = prune()
        if deleted:
            logger.info("Cleanup: {} gesprochene(r) Beispielsatz/-saetze geloescht", deleted)
        return deleted
    except Exception as e:
        logger.warning("Cleanup Aussprache-Vorrat fehlgeschlagen: {}", e)
        return 0
