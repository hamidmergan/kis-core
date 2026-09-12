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
    PODCAST_LINE_PAUSE,
    PODCAST_SOFT_TIME_LIMIT,
    PODCAST_TIME_LIMIT,
    PODCAST_TTS_PARALLELISM,
)
from src.storage import save_result_and_evict, save_result_file, save_result_meta
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled, tts_client
from src.utils.heartbeat import job_heartbeat

# The provider stumbles now and then, these pauses are enough to get past it.
_WIEDERHOLUNGEN = (2.0, 5.0, 10.0)


def _person(params: PodcastParams, line: Line):
    return params.persons[line.speaker] if line.speaker < len(params.persons) else params.persons[0]


def _stimme(params: PodcastParams, line: Line) -> str:
    return _person(params, line).voice_id


def _sprich(client, text: str, voice_id: str, sprache: str) -> bytes:
    """One contribution, split into pieces the provider can hold in 60 seconds."""
    from src.services.openai_compat_tts import _split_text

    teile = _split_text(text)
    return b"".join(
        client.synthesize_chunk(teil, voice_id=voice_id, speed=1.0, language=sprache)
        for teil in teile
    )


def _mit_wiederholung(client, text: str, voice_id: str, sprache: str) -> bytes:
    import time

    letzter: Exception | None = None
    for pause in (0.0, *_WIEDERHOLUNGEN):
        if pause:
            time.sleep(pause)
        try:
            return _sprich(client, text, voice_id, sprache)
        except Exception as e:  # noqa: BLE001 — jeder Anbieterfehler wird gleich behandelt
            letzter = e
            logger.warning("Podcast: Vertonung gescheitert, neuer Versuch in {}s: {}", pause, e)
    raise RuntimeError(str(letzter))


@celery_app.task(
    bind=True,
    name="podcast.render",
    queue="general",
    acks_late=True,
    soft_time_limit=PODCAST_SOFT_TIME_LIMIT,
    time_limit=PODCAST_TIME_LIMIT,
)
def run_podcast_render(self, job_uuid: str, user_id: int, locale: str = "de"):
    """Voices what changed, keeps what did not, and saves the finished MP3."""
    offen_idx = -1
    try:
        assert_not_cancelled(job_uuid)
        params = store.load_params(user_id, job_uuid)
        zeilen = store.load_lines(user_id, job_uuid)
        if not params or not zeilen:
            raise RuntimeError("Auftrag ohne Skript oder ohne Einstellungen")

        vertont = store.load_voiced(user_id, job_uuid)
        # A contribution keeps its audio as long as text, voice and tempo match.
        behalten = [i for i, l in enumerate(zeilen)
                    if not store.needs_voice(l, vertont, _stimme(params, l), 1.0)
                    and store.has_line_audio(user_id, job_uuid, l.id)]
        offen = [i for i in range(len(zeilen)) if i not in set(behalten)]
        fertig = set(behalten)
        sperre = threading.Lock()

        def melde() -> None:
            db.update_job_status(job_uuid, "running", progress={
                "step": "tts",
                "current": len(fertig) - len(behalten),
                "total": len(offen),
                "fertig": sorted(fertig),
                "behalten": sorted(behalten),
            })

        melde()
        # One client per provider, several voices of one provider share it.
        clients: dict[int, object] = {}

        def client_fuer(provider_id: int):
            with sperre:
                if provider_id not in clients:
                    clients[provider_id] = tts_client(provider_id)
                return clients[provider_id]

        def eine(i: int) -> int:
            assert_not_cancelled(job_uuid)
            line = zeilen[i]
            person = _person(params, line)
            if not person.voice_id:
                raise RuntimeError(f"Beitrag {i + 1} hat keine Stimme")
            stimme = person.voice_id
            ton = _mit_wiederholung(client_fuer(person.provider_id or params.provider_id),
                                    line.text, stimme, params.language)
            store.save_line_audio(user_id, job_uuid, line.id, ton)
            with sperre:
                vertont[line.id] = store.fingerprint(line, stimme, 1.0)
                store.save_voiced(user_id, job_uuid, vertont)
                fertig.add(i)
                melde()
            return i

        with job_heartbeat(job_uuid):
            if offen:
                with ThreadPoolExecutor(max_workers=min(PODCAST_TTS_PARALLELISM, len(offen))) as pool:
                    auftraege = {pool.submit(eine, i): i for i in offen}
                    for future, i in auftraege.items():
                        try:
                            future.result()
                        except JobCancelled:
                            raise
                        except Exception:
                            # The first failing contribution names the place to continue from.
                            if offen_idx < 0 or i < offen_idx:
                                offen_idx = i
                if offen_idx >= 0:
                    raise RuntimeError(f"Beitrag {offen_idx + 1} konnte nicht vertont werden")

            assert_not_cancelled(job_uuid)
            db.update_job_status(job_uuid, "running", progress={"step": "montage"})
            stuecke = [store.get_line_audio(user_id, job_uuid, l.id) for l in zeilen]
            ton, dauer = montage.kleben([s for s in stuecke if s], PODCAST_LINE_PAUSE, job_uuid)

        db.update_job_status(job_uuid, "running", progress={"step": "saving"})
        namen = [params.persons[l.speaker].name if l.speaker < len(params.persons)
                 else params.persons[0].name for l in zeilen]
        store.save_transcript(user_id, job_uuid,
                              "\n\n".join(f"{n}: {l.text}" for n, l in zip(namen, zeilen)) + "\n")
        pfad = save_result_file(user_id, job_uuid, ".mp3", ton)
        save_result_meta(user_id, job_uuid, {
            "seconds": round(dauer, 1),
            "lines": len(zeilen),
            "voices": len({l.speaker for l in zeilen}),
            "language": params.language,
            "voice_label": params.voice_label,
        })
        save_result_and_evict(user_id, job_uuid, pfad, "podcast.mp3")
        db.update_job_status(job_uuid, "success", progress={
            "step": "done", "fertig": sorted(range(len(zeilen))), "behalten": sorted(behalten),
        })
        logger.info("Podcast {}: fertig, {:.0f}s aus {} Beiträgen", job_uuid[:8], dauer, len(zeilen))
        return {"seconds": round(dauer, 1)}

    except JobCancelled:
        db.reset_job_to_awaiting(job_uuid)
        return {"cancelled": True}
    except Exception as e:
        logger.error("Podcast-Vertonung {} fehlgeschlagen: {}", job_uuid[:8], e)
        meldung = (t("podcast.lineFailed", locale, n=offen_idx + 1) if offen_idx >= 0
                   else t("podcast.renderFailed", locale))
        db.update_job_status(job_uuid, "failed", error_message=meldung)
        raise
