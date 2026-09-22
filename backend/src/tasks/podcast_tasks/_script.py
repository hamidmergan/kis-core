"""Celery task: the material of a run into a conversation."""

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.podcast import script as skript
from src.features.podcast import store
from src.i18n import t
from src.limits import STAGE_SOFT_TIME_LIMIT, STAGE_TIME_LIMIT
from src.services.job_recovery import still_mine
from src.services.job_statistik import messe, route_kennung
from src.tasks._stage import StageContinue, StageLost, continue_stage
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled
from src.utils.heartbeat import job_heartbeat

# One retry is enough: a second bad answer is a prompt problem, not chance.
_VERSUCHE = 2



@celery_app.task(
    bind=True,
    name="podcast.script",
    queue="general",
    acks_late=True,
    soft_time_limit=STAGE_SOFT_TIME_LIMIT,
    time_limit=STAGE_TIME_LIMIT,
)
def run_podcast_script(self, job_uuid: str, user_id: int, locale: str = "de",
                       etappe: int = 1, versuch: int = 0):
    """Writes script.json and hands the job back to the person."""
    try:
        assert_not_cancelled(job_uuid)
        if not still_mine(job_uuid, versuch):
            raise StageLost(job_uuid)

        # The material of the run, laid down before the task was queued.
        quelle = store.load_source(user_id, job_uuid)
        if not quelle.strip():
            raise RuntimeError(t("podcast.noContent", locale))

        assert_not_cancelled(job_uuid)
        params = store.load_params(user_id, job_uuid)
        if not params:
            raise RuntimeError("Auftrag ohne Einstellungen")

        db.update_job_status(job_uuid, "running", progress={"step": "script"})
        nachrichten = skript.build_messages(quelle, params)

        from src.services import feature_router
        from src.services.json_llm import call_json_llm

        binding = feature_router.resolve("chat")
        llm = feature_router.make_llm_client(binding)

        letzter = ""
        with job_heartbeat(job_uuid), messe(user_id, job_uuid, "skript") as zahlen:
            zahlen.update(route_kennung("chat"))
            zahlen["zeichen"] = len(quelle)
            zahlen["personen"] = len(params.persons)
            zahlen["rollen"] = ", ".join(person.role for person in params.persons)
            for versuch_nr in range(1, _VERSUCHE + 1):
                assert_not_cancelled(job_uuid)
                zahlen["versuche"] = versuch_nr
                antwort = call_json_llm(
                    llm, nachrichten, endpoint="podcast").choices[0].message.content or ""
                try:
                    zeilen = skript.parse_answer(antwort, len(params.persons))
                    break
                except skript.ScriptUnusable as e:
                    letzter = str(e)
                    logger.warning("Podcast-Skript Versuch {} unbrauchbar: {}", versuch_nr, e)
            else:
                raise RuntimeError(letzter or "Das Modell lieferte kein brauchbares Skript")
            zahlen["beitraege"] = len(zeilen)

        zeilen = store.next_ids(zeilen)
        store.save_script(user_id, job_uuid, zeilen)
        store.save_user_script(user_id, job_uuid, zeilen)
        db.update_job_status(job_uuid, "awaiting_user", progress={"step": "script_done"})
        logger.info("Podcast {}: Skript mit {} Beiträgen", job_uuid[:8], len(zeilen))
        return {"lines": len(zeilen)}

    except StageContinue:
        continue_stage(self, [job_uuid, user_id, locale, etappe + 1, versuch], job_uuid)
        return {"etappe": etappe}
    except StageLost:
        logger.info("Podcast {}: Etappe gehoert nicht mehr uns, nichts getan", job_uuid[:8])
        return {"lost": True}
    except JobCancelled:
        db.reset_job_to_awaiting(job_uuid)
        return {"cancelled": True}
    except Exception as e:
        logger.error("Podcast-Skript {} fehlgeschlagen: {}", job_uuid[:8], e)
        db.update_job_status(job_uuid, "failed",
                             error_message=t("podcast.scriptFailed", locale))
        raise
