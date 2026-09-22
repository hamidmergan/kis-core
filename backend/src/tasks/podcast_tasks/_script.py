"""Celery task: die Quellen in Aussagen, die Aussagen in ein Gespraech."""

import asyncio
import json

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.podcast import script as skript
from src.features.podcast import store
from src.i18n import t
from src.security.usage_log import log_llm_response
from src.limits import (
    FACTS_MIN_WINDOW_TOKENS,
    FACTS_OUTPUT_TOKENS,
    FACTS_PROMPT_TOKENS,
    STAGE_SOFT_TIME_LIMIT,
    STAGE_TIME_LIMIT,
)
from src.services import facts as fk
from src.services import facts_reading as fr
from src.services import sources as quellen
from src.services.job_files import JobState, parse_job_json, read_job_text, write_job_text
from src.services.job_recovery import still_mine
from src.services.job_statistik import messe, route_kennung
from src.tasks._stage import StageClock, StageContinue, StageLost, continue_stage
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled
from src.utils.heartbeat import job_heartbeat

# One retry is enough: a second bad answer is a prompt problem, not chance.
_VERSUCHE = 2


# Die Lesestuecke eines Laufs, sie ueberleben eine abgebrochene Etappe.
_SLICES_FILE = "slices.json"
_POOL_FILE = "pool.json"


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


def _material_budget(fenster: int) -> int:
    """Wie viele Zeichen Vorrat der Skriptaufruf tragen darf.

    Aus demselben gemessenen Fenster wie die Lesephase. Ein unvermessenes Modell
    bekommt den vorsichtigen Wert, der auf jedes zugelassene Fenster passt.
    """
    from src.services.model_limits import CHARS_PER_TOKEN

    if not fenster:
        fenster = FACTS_MIN_WINDOW_TOKENS
    passt = int((fenster - FACTS_OUTPUT_TOKENS - FACTS_PROMPT_TOKENS) * CHARS_PER_TOKEN)
    return max(20_000, passt)


def _fenster() -> int:
    """Das gemessene Fenster des Modells, 0 wenn es keines gibt."""
    from src.services import feature_router
    from src.services.model_limits import ensure_profile

    try:
        binding = feature_router.resolve("chat")
        profil = ensure_profile(binding.provider, binding.model or "")
        return profil.window_tokens if profil.measured else 0
    except Exception as e:  # noqa: BLE001 - ohne Messung laeuft der Auftrag einfach los
        logger.warning("Podcast: Modell nicht vermessbar ({})", e)
        return 0


def _vorrat(user_id: int, job_uuid: str, quellenliste, sprache: str, llm,
            versuch: int, clock: StageClock):
    """Der Vorrat des Laufs, einmal gelesen und danach nur noch nachgeschlagen."""
    roh = parse_job_json(job_uuid, _POOL_FILE,
                         read_job_text(user_id, job_uuid, _POOL_FILE), None)
    if roh:
        gemerkt = [f for f in (fk.from_dict(e) for e in roh if isinstance(e, dict)) if f]
        if gemerkt:
            return gemerkt

    db.update_job_status(job_uuid, "running", progress={"step": "lesen"})
    teile = fr.plan_slices(quellenliste, fr.slice_chars(_fenster()))
    speicher = _LeseSpeicher(user_id, job_uuid, versuch)
    logger.info("Podcast {}: {} Quelle(n) in {} Leseaufruf(en)",
                job_uuid[:8], len(quellenliste), len(teile))

    async def _lesen(teil):
        return await fr.read_slice(llm._async_client, llm._model, teil=teil,
                                   sources=quellenliste, language=sprache,
                                   book=lambda a: log_llm_response("podcast", llm, a))

    async def _alles():
        return await fr.map_slices(teile, read=_lesen, store=speicher, should_stop=clock.over)

    try:
        gelesen = asyncio.run(_alles())
    except fr.RunInterrupted:
        raise StageContinue from None
    vorrat = fk.build_pool(fr.by_source(gelesen, teile, len(quellenliste)))
    if vorrat:
        write_job_text(user_id, job_uuid, _POOL_FILE,
                       json.dumps([f.as_dict() for f in vorrat], ensure_ascii=False))
    logger.info("Podcast {}: {} Aussagen im Vorrat", job_uuid[:8], len(vorrat))
    return vorrat


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

        # Die Quellen des Laufs, gelesen bevor die Aufgabe eingereiht wurde.
        quellenliste = quellen.load_sources(user_id, job_uuid)
        if not quellenliste:
            raise RuntimeError(t("podcast.noContent", locale))

        assert_not_cancelled(job_uuid)
        params = store.load_params(user_id, job_uuid)
        if not params:
            raise RuntimeError("Auftrag ohne Einstellungen")

        from src.services import feature_router
        from src.services.json_llm import call_json_llm

        binding = feature_router.resolve("chat")
        llm = feature_router.make_llm_client(binding)

        clock = StageClock()
        vorrat = _vorrat(user_id, job_uuid, quellenliste, params.language, llm, versuch, clock)
        if not vorrat:
            raise RuntimeError(t("podcast.noContent", locale))

        db.update_job_status(job_uuid, "running", progress={"step": "script"})
        nachrichten = skript.build_messages(
            fk.material_block(vorrat, _material_budget(_fenster())), params)

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
