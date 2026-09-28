"""Core render pipeline: images, TTS, clips, concat, faststart."""

import asyncio
import json
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from src import database as db
from src.limits import RENDER_MAX_WORKERS, STAGE_SECONDS
from src.services.job_recovery import still_mine
from src.tasks._stage import StageContinue, StageLost
from src.utils.heartbeat import job_heartbeat
from src.storage import (
    audio_folien_mit_ton,
    clear_render_cache,
    get_job_file,
    load_result_meta,
    save_audio_cache,
    save_job_file,
    save_result_file,
    save_result_meta,
)

from src.services.screencast.auswahl import clip_paare, folien_auswahl, ton_plaetze, zu_sprechende_folien
from src.services.job_statistik import (
    anbieter_und_modell,
    messe,
    zeichen_zahlen,
)

from src.tasks.screencast_tasks._shared import (
    _JobCancelled,
    _assert_not_cancelled,
    _get_pptx_for_render,
    _get_screencast_helpers,
    _get_tts_client,
)


def _fortschritt_vertonung(
    fertige: set[int],
    zu_sprechen: int,
    gesprochen: int,
    nicht_dabei: set[int] | None = None,
) -> dict:
    """The counter means the newly spoken slides, ``fertige`` carries the preview."""
    return {
        "step": "tts",
        "current": gesprochen,
        "total": zu_sprechen,
        "fertig": sorted(fertige),
        "nicht_dabei": sorted(nicht_dabei or []),
    }


def _anders_gesprochen(user_id: int, job_uuid: str, name: str, provider_id: int, voice_id: str) -> bool:
    """True when the stored record names another provider or voice than the one this run speaks with."""
    try:
        stand = json.loads(get_job_file(user_id, job_uuid, name))
    except Exception:
        return False
    # The pin names the voice that really spoke, older records without one only know that voice.
    gesprochen = stand.get("tts_pin") or stand
    return int(gesprochen.get("provider_id") or 0) != int(provider_id or 0) or gesprochen.get("voice_id") != voice_id


def _rueckfall_ton_fremd(user_id: int, job_uuid: str, provider_id: int, voice_id: str,
                         tts_pin: dict | None) -> bool:
    """True when old audio and this run differ and a fallback spoke on either side, nobody chose that mix."""
    if not _anders_gesprochen(user_id, job_uuid, "vertonter_stand.json", provider_id, voice_id):
        return False
    try:
        alt = json.loads(get_job_file(user_id, job_uuid, "vertonter_stand.json")).get("tts_pin") or {}
    except Exception:
        alt = {}
    return bool(alt.get("fallback") or (tts_pin or {}).get("fallback"))


def _ton_fuer_ablage(audio_paths: list, plaetze: list[bool], alles_ersetzen: bool) -> list[bytes | None]:
    """None leaves the old audio of a slide, empty bytes drop audio that another voice spoke."""
    ablage: list[bytes | None] = []
    for p, platz in zip(audio_paths, plaetze):
        if platz:
            ablage.append(p.read_bytes() if p is not None and p.exists() else b"")
        else:
            ablage.append(b"" if alles_ersetzen else None)
    return ablage


def _run_render_pipeline(
    job_uuid: str,
    scripts: list[str],
    voice_id: str,
    speed: float,
    slide_pause: float,
    slide_images_override: list[Path] | None = None,
    dpi: int = 100,
    provider_id: int = 0,
    is_admin: bool = False,
    subtitles: bool = False,
    voice_label: str = "",
    video_folien: list[int] | None = None,
    neu_vertonen: list[int] | None = None,
    tts_pin: dict | None = None,
    clock=None,
    token: int = 0,
) -> dict:
    """The render path: reads the PPTX from the job folder and stores everything there."""
    (
        IMAGE_TMP_DIR,
        _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
        _create_slide_video, _concatenate_videos, _apply_faststart,
        _extract_text_per_slide,
        _create_outro_image, _get_image_dimensions,
    ) = _get_screencast_helpers()

    tts_client = _get_tts_client(provider_id)

    # Resolve user_id once for storage keying
    job_row = db.get_job(job_uuid)
    if not job_row:
        raise RuntimeError(f"Job {job_uuid} not found")
    user_id = job_row["user_id"]
    # Audio of another provider or voice never shares a video with the audio of this run.
    if _anders_gesprochen(user_id, job_uuid, "render_params.json", provider_id, voice_id):
        clear_render_cache(user_id, job_uuid)
    # A voice change the person made keeps unticked slides, a fallback on either side replaces all of them.
    alter_ton_fremd = _rueckfall_ton_fremd(user_id, job_uuid, provider_id, voice_id, tts_pin)
    if alter_ton_fremd:
        neu_vertonen = list(range(len(scripts)))
    auswahl = folien_auswahl(len(scripts), video_folien, neu_vertonen)

    # Save render params + scripts for crash recovery (retry button)
    save_job_file(user_id, job_uuid, "render_params.json", json.dumps({
        "voice_id": voice_id, "speed": speed,
        "slide_pause": slide_pause, "dpi": dpi,
        "provider_id": provider_id, "subtitles": subtitles,
        "voice_label": voice_label, "tts_pin": tts_pin,
        "video_folien": auswahl.clip_folien,
        "neu_vertonen": sorted(neu_vertonen or []),
    }).encode())
    save_job_file(user_id, job_uuid, "render_scripts.json", json.dumps(scripts).encode())

    # Check for cancellation before it starts.
    _assert_not_cancelled(job_uuid)

    db.update_job_status(job_uuid, "running", progress={"step": "images"})

    # A watcher thread checks for cancellation and kills running ffmpeg processes.
    _stop_watcher = threading.Event()
    _cancelled_by_watcher = threading.Event()

    def _cancel_watcher() -> None:
        try:
            import redis as _redis
            _r = _redis.from_url(os.environ.get("REDIS_URL", "redis://kis-redis:6379/0"))
            while not _stop_watcher.wait(0.5):
                exists = bool(_r.exists(f"job:cancel:{job_uuid}"))
                if exists:
                    logger.info("Cancel watcher: killing procs for {}", job_uuid[:8])
                    _cancelled_by_watcher.set()
                    from src.services.screencast import kill_job_procs
                    kill_job_procs(job_uuid)
                    break
        except Exception as e:
            logger.warning("Cancel watcher error: {}", e)

    threading.Thread(target=_cancel_watcher, daemon=True, name=f"cancel-{job_uuid[:8]}").start()

    try:
      with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Pre-rendering happens per resolution, if it does not match it is rendered again.
        prerendered_dir = IMAGE_TMP_DIR / job_uuid
        with messe(user_id, job_uuid, "bilder") as bild_zahlen:
            bild_zahlen["dpi"] = dpi
            if slide_images_override is not None:
                slide_images = slide_images_override
                bild_zahlen["vorrat_genutzt"] = False
            else:
                dpi_dir = prerendered_dir / f"dpi{dpi}"
                prerendered_images = sorted(dpi_dir.glob("slide-*.png")) if dpi_dir.exists() else []
                bild_zahlen["vorrat_genutzt"] = bool(prerendered_images)

                if prerendered_images:
                    logger.info(
                        "Render {}: using {} pre-rendered images ({} DPI)",
                        job_uuid, len(prerendered_images), dpi,
                    )
                    slide_images = prerendered_images
                else:
                    pptx_data = _get_pptx_for_render(user_id, job_uuid)
                    pptx_path = tmp / "render.pptx"
                    pptx_path.write_bytes(pptx_data)
                    img_dir = tmp / "images"
                    img_dir.mkdir()
                    # No units here, so the clock has to speak for this phase.
                    with job_heartbeat(job_uuid):
                        slide_images = asyncio.run(
                            _convert_slides_to_images_async(pptx_path, img_dir, dpi))
            bild_zahlen["folien"] = len(slide_images)

        _assert_not_cancelled(job_uuid)
        if _cancelled_by_watcher.is_set():
            raise _JobCancelled()

        # These slides are already finished and belong in the preview right away.
        schon_da = audio_folien_mit_ton(user_id, job_uuid) & auswahl.alter_ton_erlaubt
        zu_sprechen = zu_sprechende_folien(auswahl.clip_folien, scripts, schon_da)
        fertige_folien: set[int] = set(schon_da)
        gesprochen = 0
        db.update_job_status(job_uuid, "running", progress=_fortschritt_vertonung(
            fertige_folien, zu_sprechen, 0, auswahl.ausgeschlossen))

        def _tts_progress(current: int, total: int, folie: int) -> None:
            nonlocal gesprochen
            if _cancelled_by_watcher.is_set():
                raise _JobCancelled()
            _assert_not_cancelled(job_uuid)
            if not still_mine(job_uuid, token):
                raise StageLost(job_uuid)
            if folie in auswahl.ausgeschlossen:
                return
            if folie not in fertige_folien and scripts[folie].strip():
                gesprochen += 1
            fertige_folien.add(folie)
            db.update_job_status(job_uuid, "running", progress=_fortschritt_vertonung(
                fertige_folien, zu_sprechen, gesprochen, auswahl.ausgeschlossen))

        # Without a known target language it stays empty, then the voicing does not guess.
        target_lang = (load_result_meta(user_id, job_uuid) or {}).get("target_lang", "")
        with messe(user_id, job_uuid, "vertonung") as ton_zahlen:
            ton_zahlen.update(zeichen_zahlen(scripts))
            ton_zahlen.update(anbieter_und_modell(provider_id, "tts"))
            ton_zahlen["stimme"] = voice_id
            ton_zahlen["stimme_name"] = voice_label
            ton_zahlen["tempo"] = speed
            ton_zahlen["sprache"] = target_lang
            tts_results = asyncio.run(_generate_all_tts(scripts, tts_client, tmp, speed, voice_id, on_slide_done=_tts_progress, job_uuid=job_uuid, user_id=user_id, provider_id=provider_id, target_lang=target_lang, zaehler=ton_zahlen, ausgeschlossen=auswahl.ausgeschlossen, alter_ton_erlaubt=auswahl.alter_ton_erlaubt, clock=clock, on_beat=lambda: db.touch_job_heartbeat(job_uuid)))
        audio_paths = [r[0] for r in tts_results]
        alignments = [r[1] for r in tts_results]

        # Slides the stage did not reach, plus the montage, belong to the next stage.
        offen = [i for i, p in enumerate(audio_paths) if p is not None and not p.exists()]
        if offen or (clock is not None and clock.spent() > STAGE_SECONDS / 2):
            logger.info("Screencast {}: {} Folien offen, naechste Etappe", job_uuid, len(offen))
            raise StageContinue

        num_slides = min(len(slide_images), len(audio_paths))
        if num_slides == 0:
            raise RuntimeError("Keine Slides verarbeitet")
        if len(slide_images) != len(audio_paths):
            # Must not happen any more but has to be logged: otherwise audio and image mismatch.
            logger.error(
                "Render {}: {} Bilder, aber {} Skripte. Video wird auf {} Folien gekürzt.",
                job_uuid, len(slide_images), len(audio_paths), num_slides,
            )

        _assert_not_cancelled(job_uuid)
        if _cancelled_by_watcher.is_set():
            raise _JobCancelled()

        # ── Video clips (parallel) ────────────────────────────────────────
        db.set_render_started_at(job_uuid)
        # The slide number stays the key, only the selection is built.
        paare = clip_paare(auswahl.clip_folien, num_slides)
        if not paare:
            raise RuntimeError("Keine Folie im Screencast")
        clip_folien = [i for _, i in paare]
        clip_paths: list[Path] = [tmp / f"clip_{pos:03d}.mp4" for pos, _ in paare]

        def _render_clip_normal(pos: int) -> None:
            i = clip_folien[pos]
            _create_slide_video(slide_images[i], audio_paths[i], clip_paths[pos], pause=slide_pause, crf=23, job_uuid=job_uuid, speed=speed)

        db.update_job_status(job_uuid, "running", progress={"step": "video", "current": 0, "total": len(clip_folien)})
        with messe(user_id, job_uuid, "clips") as clip_zahlen:
            clip_zahlen["folien"] = len(clip_folien)
            clip_zahlen["nicht_dabei"] = len(auswahl.ausgeschlossen)
            clip_zahlen["folienpause"] = slide_pause
            clip_zahlen["gleichzeitig"] = RENDER_MAX_WORKERS
            with ThreadPoolExecutor(max_workers=RENDER_MAX_WORKERS) as executor:
                futures = {executor.submit(_render_clip_normal, pos): pos for pos in range(len(clip_folien))}
                completed = 0
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception:
                        # If watcher killed ffmpeg, convert to _JobCancelled
                        if _cancelled_by_watcher.is_set():
                            raise _JobCancelled()
                        raise
                    completed += 1
                    db.update_job_status(job_uuid, "running", progress={"step": "video", "current": completed, "total": len(clip_folien)})
                    if _cancelled_by_watcher.is_set():
                        raise _JobCancelled()
                    _assert_not_cancelled(job_uuid)

        # ── AI notice (same slide at the start and the end, 3s silent) ────
        _assert_not_cancelled(job_uuid)
        if _cancelled_by_watcher.is_set():
            raise _JobCancelled()
        from src.services.screencast.outro import rahme_clips
        hat_sprache = [audio_paths[i] is not None for i in clip_folien]
        hinweis_clip = None
        try:
            hinweis_w, hinweis_h = _get_image_dimensions(slide_images[clip_folien[0]])
            hinweis_img = tmp / "ki_hinweis.png"
            hinweis_clip = tmp / "clip_ki_hinweis.mp4"
            _create_outro_image(hinweis_w, hinweis_h, hinweis_img)
            _create_slide_video(hinweis_img, None, hinweis_clip, pause=0.0, crf=23, job_uuid=job_uuid, silent_duration=3.0)
        except Exception as e:
            hinweis_clip = None
            logger.warning("KI-Hinweis konnte nicht erzeugt werden, das Video laeuft ohne: {}", e)
        # The notice has to come before the subtitle track, otherwise every timestamp is off.
        clip_paths, hat_sprache = rahme_clips(clip_paths, hat_sprache, hinweis_clip)

        # ── Subtitles (own track, not burned in) ──────────────────────────
        spur_pfad = None
        spur_sprache = ""
        if subtitles:
            db.update_job_status(job_uuid, "running", progress={"step": "subtitles"})
            from src.services.screencast.subtitles import create_subtitle_track, vtt_sprachkennung
            with messe(user_id, job_uuid, "untertitel") as spur_zahlen:
                spur_zahlen["folien_mit_ton"] = sum(1 for hat in hat_sprache if hat)
                spur_pfad = create_subtitle_track(clip_paths, tmp, hat_sprache)
                spur_sprache = vtt_sprachkennung(target_lang)
                spur_zahlen["sprache"] = spur_sprache
                if spur_pfad is not None:
                    save_job_file(user_id, job_uuid, "untertitel.vtt", spur_pfad.read_bytes())

        # ── Concatenate ───────────────────────────────────────────────────
        _assert_not_cancelled(job_uuid)
        if _cancelled_by_watcher.is_set():
            raise _JobCancelled()
        db.update_job_status(job_uuid, "running", progress={"step": "concat"})
        concat_path = tmp / "concat.mp4"
        # Two long ffmpeg runs without units of their own, so the clock speaks for them.
        with job_heartbeat(job_uuid), messe(user_id, job_uuid, "zusammenfuegen") as fuege_zahlen:
            fuege_zahlen["clips"] = len(clip_paths)
            _concatenate_videos(clip_paths, concat_path)

            # ── Faststart ─────────────────────────────────────────────────
            db.update_job_status(job_uuid, "running", progress={"step": "faststart"})
            final_path = tmp / "final.mp4"
            output_bytes = _apply_faststart(concat_path, final_path, spur_pfad, spur_sprache)
            fuege_zahlen["video_bytes"] = len(output_bytes)

        # ── Save audio cache ──────────────────────────────────────────────
        db.update_job_status(job_uuid, "running", progress={"step": "saving"})
        save_audio_cache(user_id, job_uuid, _ton_fuer_ablage(
            audio_paths, ton_plaetze(len(scripts), clip_folien), alter_ton_fremd))

        # ── Save result ───────────────────────────────────────────────────
        result_path = save_result_file(user_id, job_uuid, ".mp4", output_bytes)

        existing_meta = load_result_meta(user_id, job_uuid) or {}
        meta = {
            **existing_meta,
            "audio_id": job_uuid,
            "audio_count": num_slides,
            "subtitles": spur_pfad is not None,
            "video_folien": auswahl.clip_folien,
        }
        save_result_meta(user_id, job_uuid, meta)

    finally:
        _stop_watcher.set()

    # Save slide images to bucket for admin before cleanup
    if is_admin and prerendered_dir.exists():
        img_paths = sorted(prerendered_dir.glob("dpi*/slide-*.png"))
        for img_path in img_paths:
            save_job_file(user_id, job_uuid, f"images/{img_path.name}", img_path.read_bytes())
        logger.info("Screencast render {}: saved {} slide images to bucket/images/", job_uuid, len(img_paths))

    # Clean up pre-rendered images after successful render
    if prerendered_dir.exists():
        import shutil
        shutil.rmtree(prerendered_dir, ignore_errors=True)

    return {
        "result_path": result_path,
        "audio_id": job_uuid,
        "audio_count": num_slides,
    }
