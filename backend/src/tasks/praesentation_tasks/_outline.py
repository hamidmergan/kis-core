"""Reads the sources into facts, plans the deck over them, hands it on to the build."""

import json

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.praesentation import gliederung, store, vorlage
from src.i18n import t
from src.security.usage_log import log_llm_response
from src.limits import STAGE_SOFT_TIME_LIMIT, STAGE_TIME_LIMIT
import asyncio

from src.services import facts as fk
from src.services import facts_reading as fr
from src.services import feature_router
from src.services.json_llm import call_json_llm
from src.services import sources as quellen
from src.services.job_files import JobState, parse_job_json, read_job_text, write_job_text
from src.services.job_recovery import still_mine
from src.tasks._stage import StageClock, StageContinue, StageLost, continue_stage
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled
from src.tasks.praesentation_tasks._build import run_praesentation_build
from src.utils.heartbeat import job_heartbeat

# Die Lesestuecke eines Laufs, sie ueberleben eine abgebrochene Etappe.
_SLICES_FILE = "slices.json"

# One retry is enough: a second bad answer is a prompt problem, not chance.
_VERSUCHE = 2



class _LeseSpeicher(JobState):
    """Was die Lesephase zwischen zwei Etappen behaelt, plus die Wacht des Laufs."""

    def __init__(self, user_id: int, job_uuid: str, versuch: int) -> None:
        self._versuch = versuch
        super().__init__(user_id, job_uuid, guard=self._wanted_and_mine)

    def _wanted_and_mine(self) -> None:
        assert_not_cancelled(self._job)
        if not still_mine(self._job, self._versuch):
            raise StageLost(self._job)

    def load_slices(self) -> dict[str, list[dict]]:
        roh = read_job_text(self._user, self._job, _SLICES_FILE)
        gemerkt = parse_job_json(self._job, _SLICES_FILE, roh, {}) or {}
        return {k: v.get("facts") or [] for k, v in gemerkt.items() if isinstance(v, dict)}

    def save_slice(self, key: str, facts: list[dict], vollstaendig: bool) -> None:
        self._guard()
        roh = read_job_text(self._user, self._job, _SLICES_FILE)
        gemerkt = parse_job_json(self._job, _SLICES_FILE, roh, {}) or {}
        gemerkt[key] = {"facts": facts, "vollstaendig": vollstaendig}
        write_job_text(self._user, self._job, _SLICES_FILE,
                       json.dumps(gemerkt, ensure_ascii=False))


def _fenster(llm) -> int:
    """Das gemessene Fenster des Modells, 0 wenn es keines gibt."""
    from src.services.model_limits import ensure_profile

    try:
        binding = feature_router.resolve("chat")
        profil = ensure_profile(binding.provider, binding.model or "")
        return profil.window_tokens if profil.measured else 0
    except Exception as e:  # noqa: BLE001 - ohne Messung laeuft der Auftrag einfach los
        logger.warning("Präsentation: Modell nicht vermessbar ({})", e)
        return 0


def _vorrat(user_id: int, job_uuid: str, quellenliste, sprache: str, llm,
            versuch: int, clock: StageClock):
    """Der Vorrat des Laufs, einmal gelesen und danach nur noch nachgeschlagen."""
    gemerkt = store.load_pool(user_id, job_uuid)
    if gemerkt:
        return gemerkt

    db.update_job_status(job_uuid, "running", progress={"step": "lesen"})
    teile = fr.plan_slices(quellenliste, fr.slice_chars(_fenster(llm)))
    speicher = _LeseSpeicher(user_id, job_uuid, versuch)
    logger.info("Präsentation {}: {} Quelle(n) in {} Leseaufruf(en)",
                job_uuid[:8], len(quellenliste), len(teile))

    async def _lesen(teil):
        return await fr.read_slice(llm._async_client, llm._model, teil=teil,
                                   sources=quellenliste, language=sprache,
                                   book=lambda a: log_llm_response("praesentation", llm, a))

    async def _alles():
        return await fr.map_slices(teile, read=_lesen, store=speicher,
                                   should_stop=clock.over)

    try:
        gelesen = asyncio.run(_alles())
    except fr.RunInterrupted:
        raise StageContinue from None
    vorrat = fk.build_pool(fr.by_source(gelesen, teile, len(quellenliste)))
    if vorrat:
        store.save_pool(user_id, job_uuid, vorrat)
    logger.info("Präsentation {}: {} Aussagen im Vorrat", job_uuid[:8], len(vorrat))
    return vorrat


@celery_app.task(bind=True, name="praesentation.outline", queue="general", acks_late=True,
                 soft_time_limit=STAGE_SOFT_TIME_LIMIT, time_limit=STAGE_TIME_LIMIT)
def run_praesentation_outline(self, job_uuid: str, user_id: int, locale: str = "de",
                              etappe: int = 1, versuch: int = 0):
    try:
        assert_not_cancelled(job_uuid)
        if not still_mine(job_uuid, versuch):
            raise StageLost(job_uuid)

        quellenliste = quellen.load_sources(user_id, job_uuid)
        if not quellenliste:
            raise RuntimeError(t("praesentation.noContent", locale))

        assert_not_cancelled(job_uuid)
        params = store.load_params(user_id, job_uuid)
        analyse = store.load_template_meta(user_id, job_uuid)
        if not params or analyse is None:
            raise RuntimeError("Auftrag ohne Vorlage oder Einstellungen")

        clock = StageClock()
        llm = feature_router.make_llm_client(feature_router.resolve("chat"))
        vorrat = _vorrat(user_id, job_uuid, quellenliste, params.language, llm, versuch, clock)
        if not vorrat:
            raise RuntimeError(t("praesentation.noContent", locale))

        db.update_job_status(job_uuid, "running", progress={"step": "outline"})
        rollen = vorlage.waehlbare_rollen(analyse)
        nachrichten = gliederung.build_messages(fk.pool_block(vorrat), params, rollen)
        letzter = ""
        with job_heartbeat(job_uuid):
            for versuch_nr in range(1, _VERSUCHE + 1):
                assert_not_cancelled(job_uuid)
                antwort = call_json_llm(llm, nachrichten, endpoint="praesentation").choices[0].message.content or ""
                try:
                    outline = gliederung.parse_answer(antwort, rollen)
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
