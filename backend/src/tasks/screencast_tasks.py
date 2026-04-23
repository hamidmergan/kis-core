"""Celery tasks: Screencast auto, translate, render (+ demo render)."""

import asyncio
import json
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import delete_file, get_file, get_job_file, save_audio_cache, save_job_file, save_result_file, save_result_json, save_result_meta, save_result_and_evict, clear_tts_audio_cache
from src.utils.heartbeat import job_heartbeat
from src.limits import (
    SCREENCAST_SOFT_TIME_LIMIT,
    SCREENCAST_TIME_LIMIT,
    SCREENCAST_AUTO_SOFT_TIME_LIMIT,
    SCREENCAST_AUTO_TIME_LIMIT,
    RENDER_MAX_WORKERS,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

class _JobCancelled(Exception):
    """Raised when the user clicked Abbrechen (Redis cancel flag is set)."""


def _assert_not_cancelled(job_uuid: str) -> None:
    """Raise _JobCancelled if a Redis cancel flag exists for this job."""
    cancelled = False
    try:
        import redis as _redis
        _r = _redis.from_url("redis://kis-redis:6379/0")
        cancelled = bool(_r.exists(f"job:cancel:{job_uuid}"))
    except Exception as e:
        logger.warning("Cancel check Redis error: {}", e)
    if cancelled:
        logger.info("Job {} cancelled — killing active procs", job_uuid[:8])
        try:
            from src.services.screencast import kill_job_procs
            kill_job_procs(job_uuid)
        except Exception as e:
            logger.warning("kill_job_procs error: {}", e)
        raise _JobCancelled()


def _get_screencast_helpers():
    """Import screencast helpers lazily to avoid circular imports."""
    from src.services.screencast import (
        IMAGE_TMP_DIR,
        apply_faststart,
        concatenate_videos,
        convert_slides_to_images_async,
        create_slide_video,
        extract_text_per_slide,
        generate_all_tts,
        pptx_to_images,
    )
    return (
        IMAGE_TMP_DIR,
        pptx_to_images, generate_all_tts, convert_slides_to_images_async,
        create_slide_video, concatenate_videos, apply_faststart,
        extract_text_per_slide,
    )


def _get_tts_client(provider: str = "elevenlabs"):
    if provider == "kokoro":
        from src.dependencies import is_kokoro_enabled, get_kokoro_client
        if not is_kokoro_enabled():
            raise RuntimeError("Kokoro TTS ist nicht aktiviert")
        client = get_kokoro_client()
        if not client or not client.is_available():
            raise RuntimeError("Kokoro Server nicht erreichbar")
        return client
    elif provider == "mylab":
        from src.dependencies import is_mylab_enabled, get_mylab_client
        if not is_mylab_enabled():
            raise RuntimeError("myLab TTS ist nicht aktiviert")
        client = get_mylab_client()
        if not client or not client.is_available():
            raise RuntimeError("myLab TTS Server nicht erreichbar")
        return client
    elif provider == "thorsten":
        from src.dependencies import is_thorsten_enabled, get_thorsten_client
        if not is_thorsten_enabled():
            raise RuntimeError("Thorsten TTS ist nicht aktiviert")
        client = get_thorsten_client()
        if not client or not client.is_available():
            raise RuntimeError("Thorsten TTS Server nicht erreichbar")
        return client
    else:
        from src.services.elevenlabs_client import ElevenLabsClient
        from src.config import Settings
        api_key = Settings().elevenlabs_api_key
        if not api_key:
            raise RuntimeError("ElevenLabs API Key nicht konfiguriert")
        return ElevenLabsClient(api_key)


def _get_pptx_for_render(save_uuid: str) -> bytes:
    """Get PPTX for rendering: corrected version if available, else translated."""
    try:
        return get_job_file(save_uuid, "corrected.pptx")
    except Exception:
        pass
    return get_job_file(save_uuid, "translated.pptx")


def _run_render_pipeline(
    job_uuid: str,
    scripts: list[str],
    voice_id: str,
    speed: float,
    slide_pause: float,
    slide_images_override: list[Path] | None = None,
    dpi: int = 100,
    provider: str = "elevenlabs",
    is_admin: bool = False,
) -> dict:
    """
    Core render pipeline. Reads PPTX from job folder (corrected.pptx or translated.pptx).
    All output files are saved to job_uuid's folder.

    Returns a dict with:
      result_path, audio_id, audio_count
    """
    (
        IMAGE_TMP_DIR,
        _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
        _create_slide_video, _concatenate_videos, _apply_faststart,
        _extract_text_per_slide,
    ) = _get_screencast_helpers()

    tts_client = _get_tts_client(provider)

    # Save render params + scripts for crash recovery (retry button)
    save_job_file(job_uuid, "render_params.json", json.dumps({
        "voice_id": voice_id, "speed": speed,
        "slide_pause": slide_pause, "dpi": dpi,
        "provider": provider,
    }).encode())
    save_job_file(job_uuid, "render_scripts.json", json.dumps(scripts).encode())

    # Check cancel flag before starting — catches cancels that arrived while
    # the task was queued or being restarted after a SIGTERM (acks_late requeue).
    _assert_not_cancelled(job_uuid)

    db.update_job_status(job_uuid, "running", progress={"step": "images"})

    # Watcher thread: runs for the ENTIRE pipeline (images + TTS + video clips)
    # Checks Redis cancel flag every 0.5s and kills active ffmpeg processes immediately.
    _stop_watcher = threading.Event()
    _cancelled_by_watcher = threading.Event()

    def _cancel_watcher() -> None:
        try:
            import redis as _redis
            _r = _redis.from_url("redis://kis-redis:6379/0")
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

        # ── Slide images ──────────────────────────────────────────────────
        if slide_images_override is not None:
            slide_images = slide_images_override
        else:
            prerendered_dir = IMAGE_TMP_DIR / job_uuid
            prerendered_images = sorted(prerendered_dir.glob("slide-*.png")) if prerendered_dir.exists() else []

            if prerendered_images and dpi == 100:
                logger.info("Render {}: using {} pre-rendered images (100 DPI)", job_uuid, len(prerendered_images))
                slide_images = prerendered_images
            else:
                pptx_data = _get_pptx_for_render(job_uuid)
                pptx_path = tmp / "render.pptx"
                pptx_path.write_bytes(pptx_data)
                img_dir = tmp / "images"
                img_dir.mkdir()
                slide_images = asyncio.run(_convert_slides_to_images_async(pptx_path, img_dir, dpi))

        _assert_not_cancelled(job_uuid)
        if _cancelled_by_watcher.is_set():
            raise _JobCancelled()

        # ── TTS ───────────────────────────────────────────────────────────
        db.update_job_status(job_uuid, "running", progress={"step": "tts", "current": 0, "total": len(scripts)})

        def _tts_progress(current: int, total: int) -> None:
            if _cancelled_by_watcher.is_set():
                raise _JobCancelled()
            _assert_not_cancelled(job_uuid)
            db.update_job_status(job_uuid, "running", progress={"step": "tts", "current": current, "total": total})

        tts_results = asyncio.run(_generate_all_tts(scripts, tts_client, tmp, speed, voice_id, on_slide_done=_tts_progress, job_uuid=job_uuid))
        audio_paths = [r[0] for r in tts_results]
        alignments = [r[1] for r in tts_results]

        num_slides = min(len(slide_images), len(audio_paths))
        if num_slides == 0:
            raise RuntimeError("Keine Slides verarbeitet")

        _assert_not_cancelled(job_uuid)
        if _cancelled_by_watcher.is_set():
            raise _JobCancelled()

        # ── Video clips (parallel) ────────────────────────────────────────
        db.set_render_started_at(job_uuid)
        clip_paths: list[Path] = [tmp / f"clip_{i:03d}.mp4" for i in range(num_slides)]

        def _render_clip_normal(i: int) -> None:
            _create_slide_video(slide_images[i], audio_paths[i], clip_paths[i], pause=slide_pause, crf=23, job_uuid=job_uuid)

        db.update_job_status(job_uuid, "running", progress={"step": "video", "current": 0, "total": num_slides})
        with ThreadPoolExecutor(max_workers=RENDER_MAX_WORKERS) as executor:
            futures = {executor.submit(_render_clip_normal, i): i for i in range(num_slides)}
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
                db.update_job_status(job_uuid, "running", progress={"step": "video", "current": completed, "total": num_slides})
                if _cancelled_by_watcher.is_set():
                    raise _JobCancelled()
                _assert_not_cancelled(job_uuid)

        # ── Concatenate ───────────────────────────────────────────────────
        _assert_not_cancelled(job_uuid)
        if _cancelled_by_watcher.is_set():
            raise _JobCancelled()
        db.update_job_status(job_uuid, "running", progress={"step": "concat"})
        concat_path = tmp / "concat.mp4"
        _concatenate_videos(clip_paths, concat_path)

        # ── Faststart ─────────────────────────────────────────────────────
        db.update_job_status(job_uuid, "running", progress={"step": "faststart"})
        final_path = tmp / "final.mp4"
        output_bytes = _apply_faststart(concat_path, final_path)

        # ── Save audio cache ──────────────────────────────────────────────
        db.update_job_status(job_uuid, "running", progress={"step": "saving"})
        audio_bytes_list = [ap.read_bytes() if ap is not None and ap.exists() else b"" for ap in audio_paths[:num_slides]]
        save_audio_cache(job_uuid, audio_bytes_list)

        # ── Save result ───────────────────────────────────────────────────
        result_path = save_result_file(job_uuid, ".mp4", output_bytes)

        meta = {
            "audio_id": job_uuid,
            "audio_count": num_slides,
        }
        save_result_meta(job_uuid, meta)

    finally:
        _stop_watcher.set()

    # Save slide images to bucket for admin before cleanup
    prerendered_dir = IMAGE_TMP_DIR / job_uuid
    if is_admin and prerendered_dir.exists():
        img_paths = sorted(prerendered_dir.glob("slide-*.png"))
        for img_path in img_paths:
            save_job_file(job_uuid, f"images/{img_path.name}", img_path.read_bytes())
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


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="screencast.translate", queue="screencast")
def run_screencast_translate(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    glossary_json: str,
    fast_mode: bool,
    source_lang: str = "DE",
    target_lang: str = "EN-US",
):
    """Translate PPTX DE→EN, extract slide texts, save artifacts, set awaiting_user."""
    try:
        db.update_job_status(job_uuid, "running", progress={"step": "translate"})

        pptx_bytes = get_file(input_path)

        # Save original DE PPTX immediately
        save_job_file(job_uuid, "original.pptx", pptx_bytes)

        from src.routes.translate import translate_pptx_content
        translated_bytes = translate_pptx_content(
            pptx_bytes, filename, glossary_json, source_lang, target_lang
        )

        (
            IMAGE_TMP_DIR,
            _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
            _create_slide_video, _concatenate_videos, _apply_faststart,
            _extract_text_per_slide,
        ) = _get_screencast_helpers()

        db.update_job_status(job_uuid, "running", progress={"step": "extract"})
        slide_texts = _extract_text_per_slide(translated_bytes)
        if not slide_texts:
            raise ValueError("Keine Slides in der Präsentation gefunden")

        # Save translated PPTX + scripts to job folder immediately
        save_job_file(job_uuid, "translated.pptx", translated_bytes)
        save_job_file(job_uuid, "scripts.txt", json.dumps(slide_texts, ensure_ascii=False, indent=2).encode("utf-8"))

        if fast_mode:
            result = {
                "slide_count": len(slide_texts),
                "slide_texts": slide_texts,
                "slide_images": [],
            }
        else:
            db.update_job_status(job_uuid, "running", progress={"step": "images"})
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                pptx_path = tmp / "translated.pptx"
                pptx_path.write_bytes(translated_bytes)
                img_dir = tmp / "images"
                img_dir.mkdir()
                slide_image_paths = asyncio.run(_convert_slides_to_images_async(pptx_path, img_dir))
                import base64
                slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in slide_image_paths]

            result = {
                "slide_count": len(slide_texts),
                "slide_texts": slide_texts,
                "slide_images": slide_images_b64,
            }

        result_path = save_result_json(job_uuid, result)
        save_result_and_evict(job_uuid, result_path, f"{Path(filename).stem}_translate.json")

        # awaiting_user: user must review scripts before render starts
        db.update_job_status(job_uuid, "awaiting_user")
        db.update_job_expiry(job_uuid, 168)  # 7 days — no resources held while waiting
        _maybe_dispatch_next(job_uuid)  # awaiting_user hält keinen Slot → nächsten Job starten

        # Clean up input file
        delete_file(input_path)

        logger.info("Screencast translate task {} completed: {} slides", job_uuid, len(slide_texts))

    except Exception as e:
        logger.error("Screencast translate task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


@celery_app.task(
    bind=True,
    name="screencast.render",
    queue="screencast",
    acks_late=True,
    max_retries=7,
    soft_time_limit=SCREENCAST_SOFT_TIME_LIMIT,
    time_limit=SCREENCAST_TIME_LIMIT,
)
def run_screencast_render(
    self,
    translate_job_uuid: str,
    scripts: list[str],
    voice_id: str,
    speed: float,
    slide_pause: float,
    original_filename: str = "screencast",
    dpi: int = 100,
    provider: str = "elevenlabs",
    voice_label: str = "",
    is_admin: bool = False,
):
    """Render final MP4 from edited scripts and stored PPTX.

    Reads PPTX from the translate job's folder (corrected.pptx or translated.pptx).
    All artifacts are saved to the same folder (single-folder workflow).
    """
    from celery.exceptions import SoftTimeLimitExceeded
    try:
        db.update_job_status(translate_job_uuid, "running", progress={
            "step": "render", "voice_id": voice_id, "voice_label": voice_label, "provider": provider,
        })
        with job_heartbeat(translate_job_uuid):
            result = _run_render_pipeline(
                job_uuid=translate_job_uuid,
                scripts=scripts,
                voice_id=voice_id,
                speed=speed,
                slide_pause=slide_pause,
                dpi=dpi,
                provider=provider,
                is_admin=is_admin,
            )

        result_filename = f"{Path(original_filename).stem if original_filename else 'screencast'}.mp4"
        with job_heartbeat(translate_job_uuid):
            save_result_and_evict(translate_job_uuid, result["result_path"], result_filename)
        db.update_job_status(translate_job_uuid, "success")
        clear_tts_audio_cache(translate_job_uuid)

        logger.info("Screencast render task {} completed", translate_job_uuid)
        _maybe_dispatch_next(translate_job_uuid)

    except _JobCancelled:
        logger.info("Screencast render task {} cancelled by user", translate_job_uuid)
        db.reset_job_to_awaiting(translate_job_uuid)
        _maybe_dispatch_next(translate_job_uuid)  # awaiting_user hält keinen Slot → nächsten Job starten

    except SoftTimeLimitExceeded:
        logger.warning("Screencast render task {} hit soft time limit", translate_job_uuid)
        db.update_job_status(translate_job_uuid, "failed", error_message="Zeitlimit überschritten. Bitte 'Wiederholen' klicken.")
        _maybe_dispatch_next(translate_job_uuid)

    except Exception as e:
        logger.error("Screencast render task {} failed: {}", translate_job_uuid, e)
        db.update_job_status(translate_job_uuid, "failed", error_message=str(e))
        _maybe_dispatch_next(translate_job_uuid)
        raise


@celery_app.task(
    bind=True,
    name="screencast.auto",
    queue="screencast",
    acks_late=True,
    soft_time_limit=SCREENCAST_AUTO_SOFT_TIME_LIMIT,
    time_limit=SCREENCAST_AUTO_TIME_LIMIT,
)
def run_screencast_auto(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    voice_id: str,
    speed: float,
    glossary_json: str,
    provider: str = "elevenlabs",
    voice_label: str = "",
    source_lang: str = "DE",
    target_lang: str = "EN-US",
    dpi: int = 100,
):
    """Full auto pipeline: translate → scripts → TTS → render."""
    from celery.exceptions import SoftTimeLimitExceeded
    try:
        db.update_job_status(job_uuid, "running", progress={
            "step": "translate", "voice_id": voice_id, "voice_label": voice_label, "provider": provider,
        })

        pptx_bytes = get_file(input_path)

        from src.routes.translate import translate_pptx_content
        translated_bytes = translate_pptx_content(
            pptx_bytes, filename, glossary_json, source_lang, target_lang
        )

        (
            IMAGE_TMP_DIR,
            _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
            _create_slide_video, _concatenate_videos, _apply_faststart,
            _extract_text_per_slide,
        ) = _get_screencast_helpers()

        db.update_job_status(job_uuid, "running", progress={"step": "extract"})
        slide_texts = _extract_text_per_slide(translated_bytes)
        if not slide_texts:
            raise ValueError("Keine Slides in der Präsentation gefunden")

        save_job_file(job_uuid, "translated.pptx", translated_bytes)

        # Generate scripts via KISSKI
        db.update_job_status(job_uuid, "running", progress={"step": "scripts", "total": len(slide_texts)})
        from src.services.kisski_client import KisskiClient
        from src.dependencies import _resolve_llm_provider
        _api_key, _base_url, _model, _provider = _resolve_llm_provider()
        if not _api_key:
            raise RuntimeError("Kein LLM-Provider konfiguriert")
        kisski_client = KisskiClient(
            api_key=_api_key,
            base_url=_base_url,
            model=_model,
            provider=_provider,
        )

        glossary_dict = None
        if glossary_json:
            try:
                glossary_dict = json.loads(glossary_json)
            except Exception:
                pass

        with job_heartbeat(job_uuid):
            scripts = asyncio.run(
                _generate_all_scripts_async(
                    slide_texts, kisski_client, glossary=glossary_dict, source_lang=source_lang, target_lang=target_lang
                )
            )

        with job_heartbeat(job_uuid):
            result = _run_render_pipeline(
                job_uuid=job_uuid,
                scripts=scripts,
                voice_id=voice_id,
                speed=speed,
                slide_pause=0.5,
                dpi=dpi,
                provider=provider,
            )

        result_filename = f"{Path(filename).stem}.mp4"
        with job_heartbeat(job_uuid):
            save_result_and_evict(job_uuid, result["result_path"], result_filename)
        db.update_job_status(job_uuid, "success")
        clear_tts_audio_cache(job_uuid)

        # Clean up input file
        delete_file(input_path)

        logger.info("Screencast auto task {} completed: {}", job_uuid, result_filename)
        _maybe_dispatch_next(job_uuid)

    except SoftTimeLimitExceeded:
        logger.warning("Screencast auto task {} hit soft time limit", job_uuid)
        db.update_job_status(job_uuid, "failed", error_message="Zeitlimit überschritten. Bitte 'Wiederholen' klicken.")
        _maybe_dispatch_next(job_uuid)

    except Exception as e:
        logger.error("Screencast auto task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        _maybe_dispatch_next(job_uuid)
        raise


@celery_app.task(bind=True, name="screencast.demo_render", queue="screencast", acks_late=True)
def run_screencast_demo_render(
    self,
    job_uuid: str,
    dpi: int = 100,
):
    """Demo render: FFmpeg pipeline with pre-existing demo audio files."""
    try:
        # Save params for crash recovery (retry button)
        save_job_file(job_uuid, "demo_params.json", json.dumps({"dpi": dpi}).encode())

        db.update_job_status(job_uuid, "running", progress={"step": "images"})

        from src.services.screencast import (
            IMAGE_TMP_DIR,
            pptx_to_images as _pptx_to_images,
            extract_text_per_slide as _extract_text_per_slide,
            create_slide_video as _create_slide_video,
            concatenate_videos as _concatenate_videos,
            apply_faststart as _apply_faststart,
        )
        from src.routes.screencast_demo import (
            _get_demo_slide_images_sync,
            _load_demo_audio_files,
            _find_demo_pptx,
        )

        # Get slide images: prefer pre-rendered or uploaded PPTX from job folder
        import base64
        prerendered_dir = IMAGE_TMP_DIR / job_uuid
        prerendered_images = sorted(prerendered_dir.glob("slide-*.png")) if prerendered_dir.exists() else []

        if prerendered_images and dpi == 100:
            slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in prerendered_images]
        else:
            pptx_data_job = None
            try:
                pptx_data_job = _get_pptx_for_render(job_uuid)
            except Exception:
                pass
            if pptx_data_job is not None:
                with tempfile.TemporaryDirectory() as tmpdir_img:
                    img_dir = Path(tmpdir_img) / "images"
                    img_dir.mkdir()
                    pptx_copy = Path(tmpdir_img) / "render.pptx"
                    pptx_copy.write_bytes(pptx_data_job)
                    image_paths = _pptx_to_images(pptx_copy, img_dir, dpi)
                    slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in image_paths]
            else:
                slide_images_b64 = _get_demo_slide_images_sync()

        # Load demo audio
        pptx_path = _find_demo_pptx()
        if pptx_path:
            slide_texts = _extract_text_per_slide(pptx_path.read_bytes())
        else:
            slide_texts = []
        num_slides_hint = len(slide_texts) or 6
        demo_audio = _load_demo_audio_files(num_slides_hint)

        if not demo_audio:
            raise RuntimeError("Keine Demo-MP3s gefunden. Lege slide_001.mp3 in backend/demo/slides/ ab.")

        num_slides = min(len(slide_images_b64), len(demo_audio))
        if num_slides == 0:
            raise RuntimeError("Keine Demo-Slides oder Audio")

        slide_pause = 0.5

        db.update_job_status(job_uuid, "running", progress={"step": "video", "total": num_slides})

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            slide_image_paths: list[Path] = []
            for i, img_b64 in enumerate(slide_images_b64[:num_slides]):
                img_path = tmp / f"slide_{i:03d}.png"
                img_path.write_bytes(base64.b64decode(img_b64))
                slide_image_paths.append(img_path)

            audio_paths: list[Path] = []
            for i, src in enumerate(demo_audio[:num_slides]):
                dst = tmp / f"audio_{i:03d}.mp3"
                dst.write_bytes(src.read_bytes())
                audio_paths.append(dst)

            db.set_render_started_at(job_uuid)
            clip_paths: list[Path] = [tmp / f"clip_{i:03d}.mp4" for i in range(num_slides)]

            def _render_clip(i: int) -> None:
                _create_slide_video(slide_image_paths[i], audio_paths[i], clip_paths[i], pause=slide_pause)

            db.update_job_status(job_uuid, "running", progress={"step": "video", "current": 0, "total": num_slides})
            with ThreadPoolExecutor(max_workers=RENDER_MAX_WORKERS) as executor:
                futures = {executor.submit(_render_clip, i): i for i in range(num_slides)}
                completed = 0
                for future in as_completed(futures):
                    future.result()
                    completed += 1
                    db.update_job_status(job_uuid, "running", progress={"step": "video", "current": completed, "total": num_slides})

            db.update_job_status(job_uuid, "running", progress={"step": "concat"})
            concat_path = tmp / "concat.mp4"
            _concatenate_videos(clip_paths, concat_path)

            final_path = tmp / "final.mp4"
            output_bytes = _apply_faststart(concat_path, final_path)

            audio_bytes_list = [ap.read_bytes() for ap in audio_paths[:num_slides]]
            save_audio_cache(job_uuid, audio_bytes_list)

            result_path = save_result_file(job_uuid, ".mp4", output_bytes)

            meta = {
                "audio_id": job_uuid,
                "audio_count": num_slides,
            }
            save_result_meta(job_uuid, meta)

        save_result_and_evict(job_uuid, result_path, "demo_screencast.mp4")
        db.update_job_status(job_uuid, "success")

        logger.info("Demo render task {} completed", job_uuid)
        _maybe_dispatch_next(job_uuid)

    except Exception as e:
        logger.error("Demo render task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        _maybe_dispatch_next(job_uuid)
        raise


async def _generate_all_scripts_async(slide_texts, kisski_client, glossary=None, source_lang="DE", target_lang="EN-US"):
    """Async wrapper for batch script generation (called via asyncio.run)."""
    return kisski_client.generate_scripts_batch(slide_texts, glossary, source_lang=source_lang, target_lang=target_lang)


# ── User-Level Queue: automatisch nächsten Job dispatchen ────────────────────

_SCREENCAST_TOOLS = ["screencast_translate", "screencast_render", "screencast_auto", "screencast_demo_render"]


def dispatch_next_screencast_job_for_user(user_id: int) -> None:
    """Dispatch the oldest queued screencast job for this user, if any."""
    job = db.get_next_queued_job(user_id, _SCREENCAST_TOOLS)
    if not job:
        return
    job_uuid = job["job_uuid"]
    try:
        params = json.loads(get_job_file(job_uuid, "queue_params.json"))
        dispatch_as = params.get("dispatch_as", "")
        if dispatch_as == "auto":
            task = run_screencast_auto.apply_async(args=[
                job_uuid, params["input_path"], params["filename"],
                params["voice_id"], params["speed"], params["glossary_json"],
                params["provider"], params["voice_label"],
                params["source_lang"], params["target_lang"],
                params.get("dpi", 100),
            ])
        elif dispatch_as == "translate":
            task = run_screencast_translate.apply_async(args=[
                job_uuid, params["input_path"], params["filename"],
                params["glossary_json"], params["fast_mode"],
                params["source_lang"], params["target_lang"],
            ])
        elif dispatch_as == "render":
            scripts = json.loads(get_job_file(job_uuid, "render_scripts.json"))
            try:
                import redis as _redis
                _r = _redis.from_url(os.environ.get("REDIS_URL", "redis://kis-redis:6379/0"))
                _r.delete(f"job:cancel:{job_uuid}")
            except Exception:
                pass
            task = run_screencast_render.apply_async(args=[
                job_uuid, scripts,
                params["voice_id"], params["speed"], params["slide_pause"],
                job["original_filename"] or "screencast.pptx",
                params["dpi"], params["provider"], params["voice_label"],
                params["is_admin"],
            ])
            db.set_render_queued_at(job_uuid)
        elif dispatch_as == "demo_render":
            task = run_screencast_demo_render.apply_async(args=[
                job_uuid,
                params["dpi"],
            ])
        else:
            logger.warning("dispatch_next: unknown dispatch_as '{}' for job {}", dispatch_as, job_uuid[:8])
            db.update_job_status(job_uuid, "failed", error_message="Interner Fehler: Unbekannter Job-Typ in Warteschlange.")
            return
        db.set_job_celery_task_id(job_uuid, task.id)
        logger.info("dispatch_next: dispatched queued job {} ({})", job_uuid[:8], dispatch_as)
    except Exception as e:
        logger.error("dispatch_next: failed to dispatch job {}: {}", job_uuid[:8], e)
        db.update_job_status(job_uuid, "failed", error_message=f"Konnte nicht aus der Warteschlange gestartet werden: {e}")


def _maybe_dispatch_next(job_uuid: str) -> None:
    """After a job finishes, try to dispatch the next queued job for that user."""
    try:
        job = db.get_job(job_uuid)
        if job:
            dispatch_next_screencast_job_for_user(job["user_id"])
    except Exception as e:
        logger.warning("_maybe_dispatch_next failed for {}: {}", job_uuid[:8], e)
