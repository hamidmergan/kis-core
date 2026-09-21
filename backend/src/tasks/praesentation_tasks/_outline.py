"""Reads the sources into facts, writes outline.json in one call, hands the deck on."""

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.praesentation import fakten as fk
from src.features.praesentation import gliederung, store, vorlage
from src.i18n import t
from src.limits import STAGE_SOFT_TIME_LIMIT, STAGE_TIME_LIMIT
from src.services import feature_router
from src.services.aia_json_llm import call_json_llm
from src.services.facts import Fact, RunInterrupted
from src.services.facts import pool as fc
from src.services.job_recovery import still_mine
from src.tasks._stage import StageClock, StageContinue, StageLost, continue_stage
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled
from src.tasks.praesentation_tasks._build import run_praesentation_build
from src.tasks.praesentation_tasks._material import build as _material_bauen
from src.utils.heartbeat import job_heartbeat

# One retry is enough: a second bad answer is a prompt problem, not chance.
_VERSUCHE = 2


def material_holen(user_id: int, job_uuid: str, versuch: int,
                   locale: str) -> tuple[list[Fact], str]:
    """The run's material, built once and then only read back.

    After a restart the pool is already there and every read call it cost is paid for,
    so nothing is read a second time.
    """
    vorrat = store.load_pool(user_id, job_uuid)
    if vorrat:
        return vorrat, ""
    schnappschuss = store.load_source(user_id, job_uuid)
    if schnappschuss.strip():
        return [], schnappschuss
    return _material_phase(job_uuid, user_id, versuch, locale)


def _material_phase(job_uuid: str, user_id: int, versuch: int,
                    locale: str) -> tuple[list[Fact], str]:
    """Reads every source into facts and lays the material down, or takes an older way.

    Runs in its own stage: one model call per source does not fit into a single one,
    and what a stage finished is in facts.json before the next one starts.
    """
    material = store.load_material(user_id, job_uuid)
    quellen = material.get("sources") or []
    if not quellen:
        raise RuntimeError("Auftrag ohne Material")
    params = store.load_params(user_id, job_uuid)
    if not params:
        raise RuntimeError("Auftrag ohne Einstellungen")

    db.update_job_status(job_uuid, "running", progress={"step": "material"})
    clock = StageClock()
    try:
        vorrat, schnappschuss = _material_bauen(user_id, job_uuid, material, params,
                                                clock, versuch)
    except RunInterrupted:
        # What was read is saved, the rest is the next stage's share.
        raise StageContinue from None
    if not vorrat and not schnappschuss.strip():
        raise RuntimeError(t("praesentation.noContent", locale))

    if vorrat:
        store.save_pool(user_id, job_uuid, vorrat)
        logger.info("Präsentation {}: {} Fakten aus {} Quellen",
                    job_uuid[:8], len(vorrat), len(quellen))
    else:
        store.save_source(user_id, job_uuid, schnappschuss)
        logger.info("Präsentation {}: keine Fakten, {} Zeichen Schnappschuss",
                    job_uuid[:8], len(schnappschuss))
    # Saved first, cleared second: the raw sources only ever carried a broken off stage.
    store.drop_material(user_id, job_uuid)
    return vorrat, schnappschuss


@celery_app.task(bind=True, name="praesentation.outline", queue="general", acks_late=True,
                 soft_time_limit=STAGE_SOFT_TIME_LIMIT, time_limit=STAGE_TIME_LIMIT)
def run_praesentation_outline(self, job_uuid: str, user_id: int, locale: str = "de",
                              etappe: int = 1, versuch: int = 0):
    try:
        assert_not_cancelled(job_uuid)
        if not still_mine(job_uuid, versuch):
            raise StageLost(job_uuid)

        vorrat, schnappschuss = material_holen(user_id, job_uuid, versuch, locale)

        assert_not_cancelled(job_uuid)
        params = store.load_params(user_id, job_uuid)
        analyse = store.load_template_meta(user_id, job_uuid)
        if not params or analyse is None:
            raise RuntimeError("Auftrag ohne Vorlage oder Einstellungen")
        db.update_job_status(job_uuid, "running", progress={"step": "outline"})

        # With a pool the outline picks the facts of every slide, without one it reads prose.
        material_text = fc.pool_block(vorrat, fk.material_budget()) if vorrat else schnappschuss
        gueltig = {f.fact_id for f in vorrat} or None
        rollen = vorlage.waehlbare_rollen(analyse)
        nachrichten = gliederung.build_messages(material_text, params, rollen,
                                                mit_nummern=bool(vorrat))
        llm = feature_router.make_llm_client(feature_router.resolve("chat"))
        letzter = ""
        with job_heartbeat(job_uuid):
            for versuch_nr in range(1, _VERSUCHE + 1):
                assert_not_cancelled(job_uuid)
                antwort = call_json_llm(llm, nachrichten, endpoint="praesentation").choices[0].message.content or ""
                try:
                    outline = gliederung.parse_answer(antwort, rollen, gueltig)
                    break
                except gliederung.Unusable as e:
                    letzter = str(e)
                    logger.warning("Präsentation {}: Gliederung Versuch {} unbrauchbar: {}", job_uuid[:8], versuch_nr, e)
            else:
                raise RuntimeError(letzter or "Das Modell lieferte keine brauchbare Gliederung")

        store.save_outline(user_id, job_uuid, outline)
        store.save_user_outline(user_id, job_uuid, outline)
        # The tool has no outline step to stop at, so the slides follow without a further click.
        db.update_job_status(job_uuid, "pending", progress={"step": "texte", "final": False})
        task = run_praesentation_build.apply_async(args=[job_uuid, user_id, locale, 1, 0, None, False])
        db.set_job_celery_task_id(job_uuid, task.id)
        logger.info("Präsentation {}: Gliederung mit {} Folien, Bau angestossen", job_uuid[:8], len(outline.rows))
        return {"slides": len(outline.rows)}

    except StageContinue:
        continue_stage(self, [job_uuid, user_id, locale, etappe + 1, versuch], job_uuid)
        return {"etappe": etappe}
    except StageLost:
        logger.info("Präsentation {}: Etappe gehört nicht mehr uns, nichts getan", job_uuid[:8])
        return {"lost": True}
    except JobCancelled:
        db.reset_job_to_awaiting(job_uuid)
        return {"cancelled": True}
    except Exception as e:
        logger.error("Präsentation-Gliederung {} fehlgeschlagen: {}", job_uuid[:8], e)
        db.update_job_status(job_uuid, "failed", error_message=t("praesentation.outlineFailed", locale))
        raise
