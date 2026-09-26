"""Celery task: das Material planen, dann die Folge in Teilen schreiben."""

import json
import math
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.podcast import script as skript
from src.features.podcast import store
from src.features.podcast.schemas import LENGTH_PLAN, Line
from src.i18n import t
from src.limits import (
    MAP_MATERIAL_MAX_CHARS,
    MAP_PASSAGE_NEIGHBOURS,
    PODCAST_LINES_PER_CALL,
    PODCAST_MAX_LINES,
    STAGE_SOFT_TIME_LIMIT,
    STAGE_TIME_LIMIT,
)
from src.services import sources as quellen
from src.services import text_map as tm
from src.services.job_files import parse_job_json, read_job_text, write_job_text
from src.services.job_recovery import still_mine
from src.services.job_statistik import messe, route_kennung
from src.tasks._stage import StageContinue, StageLost, continue_stage
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled
from src.utils.heartbeat import job_heartbeat

# One retry is enough: a second bad answer is a prompt problem, not chance.
_VERSUCHE = 2

_MAP_FILE = "grundlage.json"
_PLAN_FILE = "plan.json"
# The last contributions a part sees of what came before it.
_BISHER_ZEILEN = 4
# Of every earlier contribution a part sees only its opening words, enough to know the subject.
_ANFANG_WORTE = 12


def _fenster(provider_id: int | None) -> int:
    """Das gemessene Fenster des Modells, 0 wenn es keines gibt."""
    from src.services.feature_provider_choices import binding_for
    from src.services.model_limits import ensure_profile

    try:
        binding = binding_for("chat", provider_id)
        profil = ensure_profile(binding.provider, binding.model or "")
        return profil.window_tokens if profil.measured else 0
    except Exception as e:  # noqa: BLE001 - ohne Messung gilt das kleinste zugelassene Fenster
        logger.warning("Podcast: Modell nicht vermessbar ({})", e)
        return 0


def _grundlage(user_id: int, job_uuid: str, karte: tm.Karte, params, llm) -> tm.Grundlage:
    """What the planning call reads: the numbered text, or its topics when it is too long."""
    from src.services.json_llm import call_json_llm

    gemerkt = tm.grundlage_aus_dict(
        parse_job_json(job_uuid, _MAP_FILE, read_job_text(user_id, job_uuid, _MAP_FILE), None), karte)
    if gemerkt:
        return gemerkt

    def _frage(nachrichten: list[list[dict]]) -> list[str | None]:
        def _eine(n):
            try:
                return call_json_llm(llm, n, endpoint="podcast").choices[0].message.content
            except Exception as e:  # noqa: BLE001 - a lost part costs its topics, not the run
                logger.warning("Podcast: Themen eines Teils nicht gelesen ({})", e)
                return None
        with ThreadPoolExecutor(max_workers=len(nachrichten)) as pool:
            return list(pool.map(_eine, nachrichten))

    g = tm.grundlage(karte, _fenster(params.llm_provider_id),
                     language="German" if params.language == "de" else "English",
                     zweck="a podcast episode for university teaching", frage=_frage)
    write_job_text(user_id, job_uuid, _MAP_FILE,
                   json.dumps(tm.grundlage_als_dict(g), ensure_ascii=False))
    logger.info("Podcast {}: {} Stellen, geplant ueber {}", job_uuid[:8], len(karte),
                "den ganzen Text" if g.modus == tm.STELLEN else f"{len(g.themen)} Themen")
    return g


def _mit_versuchen(llm, nachrichten: list[dict], lesen, job_uuid: str, was: str):
    """One call, tried again once when the answer cannot be used."""
    from src.services.json_llm import call_json_llm

    letzter = ""
    for versuch_nr in range(1, _VERSUCHE + 1):
        assert_not_cancelled(job_uuid)
        antwort = call_json_llm(llm, nachrichten, endpoint="podcast").choices[0].message.content or ""
        try:
            return lesen(antwort)
        except skript.ScriptUnusable as e:
            letzter = str(e)
            logger.warning("Podcast {}: {} Versuch {} unbrauchbar: {}", job_uuid[:8], was, versuch_nr, e)
    raise RuntimeError(letzter or f"Das Modell lieferte kein brauchbares Ergebnis ({was})")


def _planen(llm, karte: tm.Karte, g: tm.Grundlage, params, teile: int, job_uuid: str) -> list[dict]:
    """The episode in parts. A plan that leaves out a whole file is asked for once more.

    Filling the passages in afterwards is not enough: a part follows its title, and a
    file no title names is talked over even when its text is right there.
    """
    dateien = [q.dateiname for q in karte.sources if q.stuecke]
    bester: list[dict] | None = None
    fehlt: list[str] = []
    hinweis: list[str] = []
    for versuch_nr in range(1, _VERSUCHE + 1):
        plan = _mit_versuchen(
            llm, skript.plan_messages(g.material, g.modus, params, teile, dateien, hinweis),
            lambda roh: skript.parse_plan(roh, lambda refs: g.stellen(refs, karte), teile),
            job_uuid, "Plan")
        luecken = (tm.zu_kurz([p["stellen"] for p in plan], karte)
                   if len(dateien) > 1 else [])
        if bester is None or len(luecken) < len(fehlt):
            bester, fehlt = plan, luecken
        if not fehlt:
            break
        hinweis = [f"{n} ({a} % of the material)" for n, a in luecken]
        logger.warning("Podcast {}: Plan Versuch {} gibt zu wenig Gewicht: {}", job_uuid[:8],
                       versuch_nr, ", ".join(f"{n} ({a} %)" for n, a in luecken))
    return bester


def _schreiben(llm, karte: tm.Karte, g: tm.Grundlage, params, job_uuid: str,
               user_id: int | None = None) -> list[Line]:
    """Plan the episode in parts, then write part after part from its own passages."""
    gesamt, _je = LENGTH_PLAN.get(params.length, LENGTH_PLAN["medium"])
    teile = max(1, math.ceil(gesamt / PODCAST_LINES_PER_CALL))
    plan = _planen(llm, karte, g, params, teile, job_uuid)
    if user_id is not None:
        # Kept for the record, the plan is what decides which file an episode talks about.
        write_job_text(user_id, job_uuid, _PLAN_FILE, json.dumps(plan, ensure_ascii=False))
    logger.info("Podcast {}: Plan mit {} Teil(en) nennt {:.0%} der Stellen", job_uuid[:8],
                len(plan), tm.abdeckung([p["stellen"] for p in plan], len(karte)))
    # A passage two parts name is told once, what none names goes to the nearest part.
    eigene = tm.exklusiv([p["stellen"] for p in plan])
    for teil, genannt, stellen in zip(plan, eigene, tm.abdecken(eigene, len(karte))):
        teil["genannt"], teil["stellen"] = genannt, stellen
    laengen = skript.teil_laengen(gesamt, len(plan))
    uebersicht = "\n".join(f"{i + 1}. {p['title']}: {p['gist']}" for i, p in enumerate(plan))
    if plan[-1].get("thread"):
        uebersicht += f"\n=> {plan[-1]['thread']}"
    zeilen: list[Line] = []
    for i, (teil, anzahl) in enumerate(zip(plan, laengen), start=1):
        db.update_job_status(job_uuid, "running", progress={"step": "script", "part": i - 1,
                                                            "total": len(plan)})
        material = karte.passagen(teil["stellen"], vorrang=teil["genannt"],
                                  nachbarn=MAP_PASSAGE_NEIGHBOURS, budget=MAP_MATERIAL_MAX_CHARS)
        nachrichten = skript.build_messages(
            material, params, anzahl=anzahl, teil=i, teile=len(plan), plan=uebersicht,
            bisher=zeilen[-_BISHER_ZEILEN:], opening=plan[0].get("opening", ""),
            thread=plan[-1].get("thread", ""),
            besprochen=[" ".join(z.text.split()[:_ANFANG_WORTE])
                        for z in zeilen[:-_BISHER_ZEILEN]])
        neue = _mit_versuchen(llm, nachrichten,
                              lambda roh: skript.parse_answer(roh, len(params.persons)),
                              job_uuid, f"Teil {i}")
        neue = skript.ohne_eigene_anrede(neue, [p.name for p in params.persons])
        zeilen.extend(neue)
        # The next part's progress tells the page to fetch this draft, the last one needs none.
        if user_id is not None and i < len(plan):
            store.save_draft(user_id, job_uuid, zeilen)
    return zeilen[:PODCAST_MAX_LINES]


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
        from src.services.feature_provider_choices import binding_for

        llm = feature_router.make_llm_client(binding_for("chat", params.llm_provider_id))
        karte = tm.Karte(quellenliste)
        if not len(karte):
            raise RuntimeError(t("podcast.noContent", locale))

        db.update_job_status(job_uuid, "running", progress={"step": "script"})
        with job_heartbeat(job_uuid), messe(user_id, job_uuid, "skript") as zahlen:
            zahlen.update(route_kennung("chat", params.llm_provider_id))
            zahlen["zeichen"] = sum(len(q.text) for q in quellenliste)
            zahlen["personen"] = len(params.persons)
            zahlen["rollen"] = ", ".join(person.role for person in params.persons)
            g = _grundlage(user_id, job_uuid, karte, params, llm)
            zeilen = _schreiben(llm, karte, g, params, job_uuid, user_id)
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
