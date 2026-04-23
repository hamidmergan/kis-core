"""Core Render-Pipeline für Screencast-Tasks: Bilder → TTS → Clips → Concat → Faststart."""

import asyncio
import json
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from src import database as db
from src.limits import RENDER_MAX_WORKERS
from src.storage import (
    save_audio_cache,
    save_job_file,
    save_result_file,
    save_result_meta,
)

from src.tasks.screencast_tasks._shared import (
    _JobCancelled,
    _assert_not_cancelled,
    _get_pptx_for_render,
    _get_screencast_helpers,
    _get_tts_client,
)


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
