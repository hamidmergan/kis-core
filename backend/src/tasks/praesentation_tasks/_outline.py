"""Plans the deck over the numbered text of the sources, hands it on to the build."""

from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.praesentation import gliederung, store, vorlage
from src.i18n import t
from src.limits import STAGE_SOFT_TIME_LIMIT, STAGE_TIME_LIMIT
from src.services import anweisung, feature_router
from src.services.feature_provider_choices import binding_for
from src.services import text_map as tm
from src.services.json_llm import call_json_llm
from src.services.upstream_errors import is_provider_refusal, is_upstream_busy
from src.services import sources as quellen
from src.services.job_recovery import attempt_failed, still_mine
from src.tasks._stage import StageContinue, StageLost, continue_stage
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled
from src.tasks.praesentation_tasks._build import run_praesentation_build
from src.utils.heartbeat import job_heartbeat

# One retry is enough: a second bad answer is a prompt problem, not chance.
_VERSUCHE = 2

_ZWECK = "a slide deck for university teaching"


def _fenster(provider_id: int | None) -> int:
    """Das gemessene Fenster des Modells, 0 wenn es keines gibt."""
    from src.services.model_limits import ensure_profile

    try:
        binding = binding_for("chat", provider_id)
        profil = ensure_profile(binding.provider, binding.model or "")
        return profil.window_tokens if profil.measured else 0
    except Exception as e:  # noqa: BLE001 - ohne Messung gilt das kleinste zugelassene Fenster
        logger.warning("Präsentation: Modell nicht vermessbar ({})", e)
        return 0


def _weg(llm, g: tm.Grundlage, params, user_id: int, job_uuid: str) -> None:
    """Decides once per run what the instruction is, a later stage reads it from the params."""
    if params.instruction_way or not anweisung.clean(params.instructions):
        return
    params.instruction_way = anweisung.entscheide(
        lambda n: call_json_llm(llm, n, endpoint="praesentation").choices[0].message.content,
        params.instructions, g.material, _ZWECK)
    # Only a subject the material lacks gets the hint, whoever typed nonsense knows it.
    params.instruction_unmatched = params.instruction_way == anweisung.WEG
    store.save_params(user_id, job_uuid, params)
    logger.info("Präsentation {}: Anweisung gilt als {}", job_uuid[:8], params.instruction_way)


def _frage(llm):
    """Several topic calls at once, one per part of the material."""
    def _alle(nachrichten: list[list[dict]]) -> list[str | None]:
        def _eine(n):
            try:
                return call_json_llm(llm, n, endpoint="praesentation").choices[0].message.content
            except Exception as e:  # noqa: BLE001 - a lost part costs its topics, not the run
                logger.warning("Präsentation: Themen eines Teils nicht gelesen ({})", e)
                return None
        with ThreadPoolExecutor(max_workers=len(nachrichten)) as pool:
            return list(pool.map(_eine, nachrichten))
    return _alle


def _grundlage(user_id: int, job_uuid: str, karte: tm.Karte, sprache: str, llm,
               provider_id: int | None = None) -> tm.Grundlage:
    """What the outline call reads: the numbered text, or its topics when it is too long."""
    gemerkt = tm.grundlage_aus_dict(store.load_map(user_id, job_uuid), karte)
    if gemerkt:
        return gemerkt
    g = tm.grundlage(karte, _fenster(provider_id), language=gliederung.SPRACHE.get(sprache, "German"),
                     zweck=_ZWECK, frage=_frage(llm))
    store.save_map(user_id, job_uuid, tm.grundlage_als_dict(g))
    logger.info("Präsentation {}: {} Stellen, geplant ueber {}", job_uuid[:8], len(karte),
                "den ganzen Text" if g.modus == tm.STELLEN else f"{len(g.themen)} Themen")
    return g


@celery_app.task(bind=True, name="praesentation.outline", queue="long", acks_late=True,
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

        llm = feature_router.make_llm_client(binding_for("chat", params.llm_provider_id))
        karte = tm.Karte(quellenliste)
        if not len(karte):
            raise RuntimeError(t("praesentation.noContent", locale))

        db.update_job_status(job_uuid, "running", progress={"step": "outline"})
        rollen = vorlage.waehlbare_rollen(analyse)
        letzter = ""
        with job_heartbeat(job_uuid):
            g = _grundlage(user_id, job_uuid, karte, params.language, llm, params.llm_provider_id)
            _weg(llm, g, params, user_id, job_uuid)
            # A deck on one subject takes what the material says on it, not a share of every file.
            fokus = anweisung.fokus(params.instructions, params.instruction_way)
            dateien = [] if fokus else [q.dateiname for q in quellenliste if q.stuecke]
            ziel = None if fokus else gliederung.ziel_folien(sum(len(q.text) for q in quellenliste))
            anteile = gliederung.folien_je_datei(karte, ziel - gliederung.RAHMEN_FOLIEN) if ziel else {}
            outline = None
            bester = 0
            hinweis: list[str] = []
            schief: list[str] = []
            for versuch_nr in range(1, _VERSUCHE + 1):
                assert_not_cancelled(job_uuid)
                nachrichten = gliederung.build_messages(g.material, params, rollen, g.modus,
                                                        dateien=dateien, ziel=ziel, fehlt=hinweis,
                                                        schief=schief, anteile=anteile)
                antwort = call_json_llm(llm, nachrichten, endpoint="praesentation").choices[0].message.content or ""
                try:
                    kandidat = gliederung.parse_answer(antwort, rollen,
                                                       lambda refs, anfang: g.stellen(refs, karte, anfang))
                except gliederung.Unusable as e:
                    letzter = str(e)
                    logger.warning("Präsentation {}: Gliederung Versuch {} unbrauchbar: {}", job_uuid[:8], versuch_nr, e)
                    continue
                # Only a deck over several files can leave one out or lean on one.
                mehrere = len(dateien) > 1
                luecken = tm.zu_kurz([r.stellen for r in kandidat.rows], karte) if mehrere else []
                schief = gliederung.schief(kandidat.rows, karte) if mehrere else []
                mangel = len(luecken) + len(schief)
                if outline is None or mangel < bester:
                    outline, bester = kandidat, mangel
                if not mangel:
                    break
                # A deck that skips or buries a file is kept only when the retry does no better.
                hinweis = [f"{n} ({a} % of the material)" for n, a in luecken]
                logger.warning("Präsentation {}: Gliederung Versuch {} unausgewogen: {} {}",
                               job_uuid[:8], versuch_nr, ", ".join(hinweis), ", ".join(schief))
            if outline is None:
                raise RuntimeError(letzter or "Das Modell lieferte keine brauchbare Gliederung")

        logger.info("Präsentation {}: Gliederung nennt {:.0%} der Stellen", job_uuid[:8],
                    tm.abdeckung([r.stellen for r in outline.rows], len(karte)))
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
        busy, nein = is_upstream_busy(e), is_provider_refusal(e)
        # While it only waits on the provider the job shows that, not the failure text.
        key = "job.providerRefused" if nein else "job.upstreamBusy" if busy else "praesentation.outlineFailed"
        attempt_failed(job_uuid, t(key, locale), busy=busy, refused=nein)
        raise
