"""Celery-Task: Demo-Render mit vorgefertigten Demo-MP3-Dateien."""

import base64
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.limits import RENDER_MAX_WORKERS
from src.storage import (
    save_audio_cache,
    save_job_file,
    save_result_and_evict,
    save_result_file,
    save_result_meta,
)

from src.tasks.screencast_tasks._queue import _maybe_dispatch_next
from src.tasks.screencast_tasks._shared import _get_pptx_for_render


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
