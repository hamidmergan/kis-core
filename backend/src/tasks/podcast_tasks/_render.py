"""Celery task: every contribution gets its voice, then one file to listen to."""

import threading
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.podcast import audio as montage
from src.features.podcast import store
from src.features.podcast.schemas import Line, PodcastParams
from src.i18n import t
from src.limits import (
    PODCAST_PAUSES,
    PODCAST_TTS_PARALLELISM,
    STAGE_SOFT_TIME_LIMIT,
    STAGE_TIME_LIMIT,
)
from src.services import tts_job_provider
from src.services.job_recovery import attempt_failed, still_mine
from src.services.job_statistik import anbieter_und_modelle, messe
from src.services.upstream_errors import is_upstream_busy
from src.storage import (
    load_result_meta,
    save_result_and_evict,
    save_result_file,
    save_result_meta,
)
from src.tasks._stage import StageClock, StageContinue, StageLost, continue_stage
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled, tts_client
from src.utils.heartbeat import job_heartbeat

# The provider stumbles now and then, these pauses are enough to get past it.
_WIEDERHOLUNGEN = (2.0, 5.0, 10.0)


def _person(params: PodcastParams, line: Line):
    return params.persons[line.speaker] if line.speaker < len(params.persons) else params.persons[0]


def _gepinnt(params: PodcastParams, pin: dict, person) -> tuple[int, str]:
    """Provider and voice this person speaks with in the current run."""
    return store.pinned_voice(pin, person.provider_id or params.provider_id, person.voice_id)


def _stimme(params: PodcastParams, pin: dict, line: Line) -> tuple[int, str]:
    return _gepinnt(params, pin, _person(params, line))


def _noch_aktuell(params: PodcastParams, pin: dict, vertont: dict, line: Line) -> bool:
    """Whether the stored audio came from exactly this text, provider, voice and tempo."""
    anbieter, stimme = _stimme(params, pin, line)
    person = _person(params, line)
    return not store.needs_voice(line, vertont, stimme, params.speed, anbieter,
                                 person.provider_id or params.provider_id)


def _festlegen(params: PodcastParams) -> dict:
    """Provider and voices of the whole run, no two persons share a voice on the provider they end up on."""
    gruppen: dict[int, list[str]] = {}
    for person in params.persons:
        stimmen = gruppen.setdefault(person.provider_id or params.provider_id, [])
        if person.voice_id and person.voice_id not in stimmen:
            stimmen.append(person.voice_id)
    # Voices in use per provider, first as chosen, then plus those the fallback took over.
    benutzt: dict[int, list[str]] = {pid: list(stimmen) for pid, stimmen in gruppen.items()}
    pin: dict = {"voices": {}, "fallback": False}
    for pid, stimmen in gruppen.items():
        if not stimmen:
            continue
        wahl = tts_job_provider.pick(pid, stimmen)
        besetzt = benutzt.get(wahl.provider_id, [])
        if wahl.fallback and set(wahl.voices) & set(besetzt):
            # Only the answer names the fallback provider, so a clash there is decided once more.
            wahl = tts_job_provider.pick(pid, stimmen, taken=besetzt)
        if wahl.fallback:
            benutzt.setdefault(wahl.provider_id, []).extend(wahl.voices)
        pin["fallback"] = pin["fallback"] or wahl.fallback
        for stimme, neu in zip(stimmen, wahl.voices):
            pin["voices"][store.pin_key(pid, stimme)] = {
                "provider_id": wahl.provider_id, "voice_id": neu}
    return pin


def _besetzung(params: PodcastParams, pin: dict) -> str:
    """Who speaks with which role, which voice and from which provider."""
    from src import database as db

    namen: dict[int, str] = {}
    teile = []
    for person in params.persons:
        pid, stimme = _gepinnt(params, pin, person)
        if pid not in namen:
            namen[pid] = (db.get_provider(pid) or {}).get("name") or ""
        angaben = [person.role, stimme, namen[pid]]
        teile.append(f"{person.name} ({', '.join(a for a in angaben if a)})")
    return ", ".join(teile)


def _stimmen_etikett(params: PodcastParams, pin: dict) -> str:
    """The page's label, unless the fallback spoke, then the names of the voices that really did."""
    if not pin.get("fallback"):
        return params.voice_label
    return ", ".join(dict.fromkeys(
        tts_job_provider.voice_name(*_gepinnt(params, pin, p)) for p in params.persons))


def _behalten_aus_vorlauf(job_uuid: str) -> list[int] | None:
    """What counted as kept when this run started, the stages before overwrote the progress."""
    import json

    job = db.get_job(job_uuid) or {}
    roh = job.get("progress")
    try:
        stand = roh if isinstance(roh, dict) else json.loads(roh or "{}")
    except (TypeError, ValueError):
        return None
    wert = stand.get("behalten")
    return wert if isinstance(wert, list) else None


def _sprich(client, text: str, voice_id: str, sprache: str, tempo: float) -> bytes:
    """One contribution, split into pieces the provider can hold in 60 seconds."""
    from src.services.openai_compat_tts import _split_text

    teile = _split_text(text)
    return b"".join(
        client.synthesize_chunk(teil, voice_id=voice_id, speed=tempo, language=sprache)
        for teil in teile
    )


def _mit_wiederholung(client, text: str, voice_id: str, sprache: str, tempo: float,
                      job_uuid: str = "", clock: StageClock | None = None) -> bytes:
    import time

    letzter: Exception | None = None
    for pause in (0.0, *_WIEDERHOLUNGEN):
        if pause:
            # Do not keep dripping against a dead provider once the stage or the job is over.
            if job_uuid:
                assert_not_cancelled(job_uuid)
            if clock is not None and clock.over():
                break
            time.sleep(pause)
        try:
            return _sprich(client, text, voice_id, sprache, tempo)
        except Exception as e:  # noqa: BLE001 — jeder Anbieterfehler wird gleich behandelt
            if getattr(e, "permanent", False):
                # A wrong key or an empty balance stays so, asking again only costs time.
                raise
            letzter = e
            logger.warning("Podcast: Vertonung gescheitert, neuer Versuch in {}s: {}", pause, e)
    raise RuntimeError(str(letzter))


@celery_app.task(
    bind=True,
    name="podcast.render",
    queue="tts",
    acks_late=True,
    soft_time_limit=STAGE_SOFT_TIME_LIMIT,
    time_limit=STAGE_TIME_LIMIT,
)
def run_podcast_render(self, job_uuid: str, user_id: int, locale: str = "de",
                       etappe: int = 1, versuch: int = 0):
    """Voices what changed, keeps what did not, and saves the finished MP3."""
    offen_idx = -1
    try:
        assert_not_cancelled(job_uuid)
        if not still_mine(job_uuid, versuch):
            raise StageLost(job_uuid)
        clock = StageClock()
        params = store.load_params(user_id, job_uuid)
        zeilen = store.load_lines(user_id, job_uuid)
        if not params or not zeilen:
            raise RuntimeError("Auftrag ohne Skript oder ohne Einstellungen")

        pin = store.load_pin(user_id, job_uuid)
        if pin is None:
            # Only the first stage of a run decides, later stages and every resume keep its choice.
            pin = _festlegen(params)
            store.save_pin(user_id, job_uuid, pin)
        vertont = store.load_voiced(user_id, job_uuid)
        # A contribution keeps its audio as long as text, provider, voice and tempo match.
        behalten = [i for i, l in enumerate(zeilen)
                    if _noch_aktuell(params, pin, vertont, l)
                    and store.has_line_audio(user_id, job_uuid, l.id)]
        # From the second stage on, what this run already voiced must not count as kept.
        aus_vorlauf = _behalten_aus_vorlauf(job_uuid) if etappe > 1 else None
        gemerkt = aus_vorlauf if aus_vorlauf is not None else behalten
        offen = [i for i in range(len(zeilen)) if i not in set(behalten)]
        fertig = set(behalten)
        # Like the screencast: a contribution is only shown once the ones before it are.
        gezeigt = set(behalten)
        freigegeben = 0
        sperre = threading.Lock()

        def melde() -> None:
            nonlocal freigegeben
            while freigegeben < len(offen) and offen[freigegeben] in fertig:
                gezeigt.add(offen[freigegeben])
                freigegeben += 1
            db.update_job_status(job_uuid, "running", progress={
                "step": "tts",
                "current": len(gezeigt) - len(gemerkt),
                "total": len(zeilen) - len(gemerkt),
                "fertig": sorted(gezeigt),
                "behalten": sorted(gemerkt),
            })

        melde()
        # One client per provider, several voices of one provider share it.
        clients: dict[int, object] = {}

        def client_fuer(provider_id: int):
            with sperre:
                if provider_id not in clients:
                    clients[provider_id] = tts_client(provider_id, user_id)
                return clients[provider_id]

        def eine(i: int) -> int | None:
            # The stage is over, this contribution belongs to the next one.
            if clock.over():
                return None
            assert_not_cancelled(job_uuid)
            if not still_mine(job_uuid, versuch):
                raise StageLost(job_uuid)
            line = zeilen[i]
            if not _person(params, line).voice_id:
                raise RuntimeError(f"Beitrag {i + 1} hat keine Stimme")
            anbieter, stimme = _stimme(params, pin, line)
            ton = _mit_wiederholung(client_fuer(anbieter),
                                    line.text, stimme, params.language, params.speed,
                                    job_uuid, clock)
            store.save_line_audio(user_id, job_uuid, line.id, ton)
            with sperre:
                vertont[line.id] = store.fingerprint(line, stimme, params.speed, anbieter)
                store.save_voiced(user_id, job_uuid, vertont)
                fertig.add(i)
                # A finished contribution is the liveness sign, no clock thread ticks for us.
                melde()
            return i

        with messe(user_id, job_uuid, "vertonung") as ton_zahlen:
            ton_zahlen.update(anbieter_und_modelle(
                [_gepinnt(params, pin, p)[0] for p in params.persons], "tts"))
            ton_zahlen["etappe"] = etappe
            ton_zahlen["sprache"] = params.language
            ton_zahlen["tempo"] = params.speed
            ton_zahlen["personen"] = len(params.persons)
            ton_zahlen["besetzung"] = _besetzung(params, pin)
            ton_zahlen["stimmen"] = len({_stimme(params, pin, l) for l in zeilen})
            ton_zahlen["beitraege"] = len(zeilen)
            ton_zahlen["neu_vertont"] = len(offen)
            ton_zahlen["behalten"] = len(gemerkt)
            ton_zahlen["zeichen"] = sum(len(l.text) for l in zeilen)
            if offen:
                ton_zahlen["gleichzeitig"] = min(PODCAST_TTS_PARALLELISM, len(offen))
                with ThreadPoolExecutor(
                        max_workers=min(PODCAST_TTS_PARALLELISM, len(offen))) as pool:
                    auftraege = {pool.submit(eine, i): i for i in offen}
                    for future, i in auftraege.items():
                        try:
                            future.result()
                        except (JobCancelled, StageLost):
                            raise
                        except Exception as fehler:
                            # The first failing contribution names the place to continue from.
                            if offen_idx < 0 or i < offen_idx:
                                offen_idx, ursache = i, fehler
                if offen_idx >= 0:
                    raise RuntimeError(f"Beitrag {offen_idx + 1} konnte nicht vertont werden") from ursache

        # Whatever the stage did not reach goes to the next one, outside the statistics.
        if [i for i in offen if i not in fertig]:
            raise StageContinue

        assert_not_cancelled(job_uuid)
        if not still_mine(job_uuid, versuch):
            raise StageLost(job_uuid)
        db.update_job_status(job_uuid, "running", progress={"step": "montage"})
        stuecke = [store.get_line_audio(user_id, job_uuid, l.id) for l in zeilen]
        with job_heartbeat(job_uuid):
            with messe(user_id, job_uuid, "montage") as montage_zahlen:
                ton, dauer = montage.kleben([s for s in stuecke if s], job_uuid)
                montage_zahlen["stuecke"] = len([s for s in stuecke if s])
                montage_zahlen["tondauer_s"] = round(dauer, 1)
                montage_zahlen["mp3_bytes"] = len(ton)
                montage_zahlen["beitragspause"] = PODCAST_PAUSES[1]

        db.update_job_status(job_uuid, "running", progress={"step": "saving"})
        namen = [params.persons[l.speaker].name if l.speaker < len(params.persons)
                 else params.persons[0].name for l in zeilen]
        store.save_transcript(user_id, job_uuid,
                              "\n\n".join(f"{n}: {l.text}" for n, l in zip(namen, zeilen)) + "\n")
        pfad = save_result_file(user_id, job_uuid, ".mp3", ton)
        # Load first: the run numbers already sit in this file and must survive.
        save_result_meta(user_id, job_uuid, {
            **(load_result_meta(user_id, job_uuid) or {}),
            "seconds": round(dauer, 1),
            "lines": len(zeilen),
            "voices": len({l.speaker for l in zeilen}),
            "language": params.language,
            "voice_label": _stimmen_etikett(params, pin),
        })
        save_result_and_evict(user_id, job_uuid, pfad, "podcast.mp3")
        db.update_job_status(job_uuid, "success", progress={
            "step": "done", "fertig": sorted(range(len(zeilen))), "behalten": sorted(gemerkt),
        })
        logger.info("Podcast {}: fertig, {:.0f}s aus {} Beiträgen", job_uuid[:8], dauer, len(zeilen))
        return {"seconds": round(dauer, 1)}

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
        logger.error("Podcast-Vertonung {} fehlgeschlagen: {}", job_uuid[:8], e)
        meldung = (t("podcast.lineFailed", locale, n=offen_idx + 1) if offen_idx >= 0
                   else t("podcast.renderFailed", locale))
        # A person's own voice service said why, that tells more than the number of the contribution.
        if hasattr(e.__cause__ or e, "vendor_label"):
            meldung = (e.__cause__ or e).message(locale)
        attempt_failed(job_uuid, meldung, busy=is_upstream_busy(e.__cause__ or e))
        raise
