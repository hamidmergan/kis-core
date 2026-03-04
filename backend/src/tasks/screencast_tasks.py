"""Celery tasks: Screencast auto, translate, render (+ demo render)."""

import asyncio
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import delete_file, get_file, get_job_file, save_audio_cache, save_job_file, save_result_file, save_result_json, save_result_meta, save_result_and_evict
from src.utils.heartbeat import job_heartbeat


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_screencast_helpers():
    """Import screencast helpers lazily to avoid circular imports."""
    from src.routes.screencast import (
        IMAGE_TMP_DIR,
        _pptx_to_images,
        _generate_all_tts,
        _convert_slides_to_images_async,
        _create_slide_video,
        _concatenate_videos,
        _apply_faststart,
        _embed_subtitles as _embed_subs,
        _get_audio_duration,
        _extract_text_per_slide,
    )
    from src.services.subtitle_converter import build_subtitles
    return (
        IMAGE_TMP_DIR,
        _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
        _create_slide_video, _concatenate_videos, _apply_faststart, _embed_subs,
        _get_audio_duration, _extract_text_per_slide,
        build_subtitles,
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
    embed_subtitles: bool,
    slide_images_override: list[Path] | None = None,
    dpi: int = 100,
    provider: str = "elevenlabs",
) -> dict:
    """
    Core render pipeline. Reads PPTX from job folder (corrected.pptx or translated.pptx).
    All output files are saved to job_uuid's folder.

    Returns a dict with:
      result_path, audio_id, audio_count, subtitle_data
    """
    (
        IMAGE_TMP_DIR,
        _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
        _create_slide_video, _concatenate_videos, _apply_faststart, _embed_subs,
        _get_audio_duration, _extract_text_per_slide,
        build_subtitles,
    ) = _get_screencast_helpers()

    tts_client = _get_tts_client(provider)

    # Save render params + scripts for crash recovery (retry button)
    save_job_file(job_uuid, "render_params.json", json.dumps({
        "voice_id": voice_id, "speed": speed,
        "slide_pause": slide_pause, "embed_subtitles": embed_subtitles, "dpi": dpi,
    }).encode())
    save_job_file(job_uuid, "render_scripts.json", json.dumps(scripts).encode())

    db.update_job_status(job_uuid, "running", progress={"step": "images"})

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

        # ── TTS ───────────────────────────────────────────────────────────
        db.update_job_status(job_uuid, "running", progress={"step": "tts", "current": 0, "total": len(scripts)})

        def _tts_progress(current: int, total: int) -> None:
            db.update_job_status(job_uuid, "running", progress={"step": "tts", "current": current, "total": total})

        with job_heartbeat(job_uuid):
            tts_results = asyncio.run(_generate_all_tts(scripts, tts_client, tmp, speed, voice_id, on_slide_done=_tts_progress, job_uuid=job_uuid))
        audio_paths = [r[0] for r in tts_results]
        alignments = [r[1] for r in tts_results]

        num_slides = min(len(slide_images), len(audio_paths))
        if num_slides == 0:
            raise RuntimeError("Keine Slides verarbeitet")

        # ── Video clips (parallel) ────────────────────────────────────────
        clip_paths: list[Path] = [tmp / f"clip_{i:03d}.mp4" for i in range(num_slides)]

        def _render_clip_normal(i: int) -> None:
            _create_slide_video(slide_images[i], audio_paths[i], clip_paths[i], pause=slide_pause, crf=23)

        db.update_job_status(job_uuid, "running", progress={"step": "video", "current": 0, "total": num_slides})
        with ThreadPoolExecutor(max_workers=max(1, os.cpu_count() // 2)) as executor:
            futures = {executor.submit(_render_clip_normal, i): i for i in range(num_slides)}
            completed = 0
            for future in as_completed(futures):
                future.result()
                completed += 1
                db.update_job_status(job_uuid, "running", progress={"step": "video", "current": completed, "total": num_slides})

        # ── Concatenate ───────────────────────────────────────────────────
        db.update_job_status(job_uuid, "running", progress={"step": "concat"})
        concat_path = tmp / "concat.mp4"
        _concatenate_videos(clip_paths, concat_path)

        # ── Subtitles ─────────────────────────────────────────────────────
        per_slide_data = []
        for i in range(num_slides):
            dur = _get_audio_duration(audio_paths[i])
            per_slide_data.append({"alignment": alignments[i], "audio_duration": dur})
        subtitle_data = build_subtitles(per_slide_data, slide_pause=slide_pause)

        if embed_subtitles and subtitle_data.get("srt"):
            db.update_job_status(job_uuid, "running", progress={"step": "subtitles"})
            srt_path = tmp / "subtitles.srt"
            srt_path.write_text(subtitle_data["srt"], encoding="utf-8")
            subtitled_path = tmp / "concat_sub.mp4"
            if _embed_subs(concat_path, srt_path, subtitled_path):
                concat_path = subtitled_path

        # ── Faststart ─────────────────────────────────────────────────────
        final_path = tmp / "final.mp4"
        output_bytes = _apply_faststart(concat_path, final_path)

        # ── Save audio cache ──────────────────────────────────────────────
        audio_bytes_list = [ap.read_bytes() if ap is not None and ap.exists() else b"" for ap in audio_paths[:num_slides]]
        save_audio_cache(job_uuid, audio_bytes_list)

        # ── Save result ───────────────────────────────────────────────────
        result_path = save_result_file(job_uuid, ".mp4", output_bytes)

        meta = {
            "subtitle_b64": __import__("base64").b64encode(
                json.dumps(subtitle_data).encode("utf-8")
            ).decode("ascii"),
            "audio_id": job_uuid,
            "audio_count": num_slides,
        }
        save_result_meta(job_uuid, meta)

        # ── Save subtitle files separately ───────────────────────────────
        for ext, key in (("srt", "subtitles.srt"), ("vtt", "subtitles.vtt"), ("txt", "transcript.txt")):
            content = subtitle_data.get(ext, "")
            if content:
                save_job_file(job_uuid, key, content.encode("utf-8"))

    # Clean up pre-rendered images after successful render
    prerendered_dir = IMAGE_TMP_DIR / job_uuid
    if prerendered_dir.exists():
        import shutil
        shutil.rmtree(prerendered_dir, ignore_errors=True)

    return {
        "result_path": result_path,
        "audio_id": job_uuid,
        "audio_count": num_slides,
        "subtitle_data": subtitle_data,
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
):
    """Translate PPTX DE→EN, extract slide texts, save artifacts, set awaiting_user."""
    try:
        db.update_job_status(job_uuid, "running", progress={"step": "translate"})

        pptx_bytes = get_file(input_path)

        # Save original DE PPTX immediately
        save_job_file(job_uuid, "original.pptx", pptx_bytes)

        from src.routes.translate import translate_pptx_content
        translated_bytes = translate_pptx_content(pptx_bytes, filename, glossary_json)

        (
            IMAGE_TMP_DIR,
            _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
            _create_slide_video, _concatenate_videos, _apply_faststart, _embed_subs,
            _get_audio_duration, _extract_text_per_slide,
            build_subtitles,
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

        # Clean up input file
        delete_file(input_path)

        logger.info("Screencast translate task {} completed: {} slides", job_uuid, len(slide_texts))

    except Exception as e:
        logger.error("Screencast translate task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


@celery_app.task(bind=True, name="screencast.render", queue="screencast", acks_late=True, max_retries=7)
def run_screencast_render(
    self,
    translate_job_uuid: str,
    scripts: list[str],
    voice_id: str,
    speed: float,
    slide_pause: float,
    embed_subtitles: bool,
    original_filename: str = "screencast",
    dpi: int = 100,
    provider: str = "elevenlabs",
):
    """Render final MP4 from edited scripts and stored PPTX.

    Reads PPTX from the translate job's folder (corrected.pptx or translated.pptx).
    All artifacts are saved to the same folder (single-folder workflow).
    """
    try:
        result = _run_render_pipeline(
            job_uuid=translate_job_uuid,
            scripts=scripts,
            voice_id=voice_id,
            speed=speed,
            slide_pause=slide_pause,
            embed_subtitles=embed_subtitles,
            dpi=dpi,
            provider=provider,
        )

        result_filename = f"{Path(original_filename).stem if original_filename else 'screencast'}.mp4"
        save_result_and_evict(translate_job_uuid, result["result_path"], result_filename)
        db.update_job_status(translate_job_uuid, "success")

        logger.info("Screencast render task {} completed", translate_job_uuid)

    except Exception as e:
        logger.error("Screencast render task {} failed: {}", translate_job_uuid, e)
        db.update_job_status(translate_job_uuid, "failed", error_message=str(e))
        raise


@celery_app.task(bind=True, name="screencast.auto", queue="screencast")
def run_screencast_auto(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    voice_id: str,
    speed: float,
    glossary_json: str,
    provider: str = "elevenlabs",
):
    """Full auto pipeline: translate → scripts → TTS → render."""
    try:
        db.update_job_status(job_uuid, "running", progress={"step": "translate"})

        pptx_bytes = get_file(input_path)

        from src.routes.translate import translate_pptx_content
        translated_bytes = translate_pptx_content(pptx_bytes, filename, glossary_json)

        (
            IMAGE_TMP_DIR,
            _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
            _create_slide_video, _concatenate_videos, _apply_faststart, _embed_subs,
            _get_audio_duration, _extract_text_per_slide,
            build_subtitles,
        ) = _get_screencast_helpers()

        db.update_job_status(job_uuid, "running", progress={"step": "extract"})
        slide_texts = _extract_text_per_slide(translated_bytes)
        if not slide_texts:
            raise ValueError("Keine Slides in der Präsentation gefunden")

        save_job_file(job_uuid, "translated.pptx", translated_bytes)

        # Generate scripts via KISSKI
        db.update_job_status(job_uuid, "running", progress={"step": "scripts", "total": len(slide_texts)})
        from src.services.kisski_client import KisskiClient
        from src.config import Settings
        _s = Settings()
        if not _s.kisski_api_key:
            raise RuntimeError("KISSKI API Key nicht konfiguriert")
        kisski_client = KisskiClient(
            api_key=_s.kisski_api_key,
            base_url=_s.kisski_base_url,
            model=_s.kisski_model,
        )

        glossary_dict = None
        if glossary_json:
            try:
                glossary_dict = json.loads(glossary_json)
            except Exception:
                pass

        scripts = asyncio.run(
            _generate_all_scripts_async(slide_texts, kisski_client, glossary=glossary_dict)
        )

        result = _run_render_pipeline(
            job_uuid=job_uuid,
            scripts=scripts,
            voice_id=voice_id,
            speed=speed,
            slide_pause=0.5,
            embed_subtitles=True,
            provider=provider,
        )

        result_filename = f"{Path(filename).stem}.mp4"
        save_result_and_evict(job_uuid, result["result_path"], result_filename)
        db.update_job_status(job_uuid, "success")

        # Clean up input file
        delete_file(input_path)

        logger.info("Screencast auto task {} completed: {}", job_uuid, result_filename)

    except Exception as e:
        logger.error("Screencast auto task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


@celery_app.task(bind=True, name="screencast.demo_render", queue="screencast", acks_late=True)
def run_screencast_demo_render(
    self,
    job_uuid: str,
    dpi: int = 100,
):
    """Demo render: FFmpeg pipeline with pre-existing demo audio files."""
    import time
    t_start = time.time()

    def _elapsed(since=None):
        return f"{time.time() - (since or t_start):.2f}s"

    try:
        # Save params for crash recovery (retry button)
        save_job_file(job_uuid, "demo_params.json", json.dumps({"dpi": dpi}).encode())

        db.update_job_status(job_uuid, "running", progress={"step": "images"})

        from src.routes.screencast import (
            IMAGE_TMP_DIR,
            _pptx_to_images,
            _get_demo_slide_images_sync,
            _load_demo_audio_files,
            _load_demo_subtitles,
            _find_demo_pptx,
            _extract_text_per_slide,
            _create_slide_video,
            _concatenate_videos,
            _apply_faststart,
            _embed_subtitles as _embed_subs,
            _get_audio_duration,
        )
        from src.services.subtitle_converter import build_subtitles

        logger.info("TIMING [{}] start", job_uuid[:8])

        # Get slide images: prefer pre-rendered or uploaded PPTX from job folder
        import base64
        t0 = time.time()
        prerendered_dir = IMAGE_TMP_DIR / job_uuid
        prerendered_images = sorted(prerendered_dir.glob("slide-*.png")) if prerendered_dir.exists() else []

        if prerendered_images and dpi == 100:
            slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in prerendered_images]
            logger.info("TIMING [{}] images: pre-rendered 100dpi ({} slides) in {}", job_uuid[:8], len(slide_images_b64), _elapsed(t0))
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
                logger.info("TIMING [{}] images: re-rendered {}dpi ({} slides) in {}", job_uuid[:8], dpi, len(slide_images_b64), _elapsed(t0))
            else:
                slide_images_b64 = _get_demo_slide_images_sync()
                logger.info("TIMING [{}] images: demo ({} slides) in {}", job_uuid[:8], len(slide_images_b64), _elapsed(t0))

        # Load demo audio
        t0 = time.time()
        pptx_path = _find_demo_pptx()
        if pptx_path:
            slide_texts = _extract_text_per_slide(pptx_path.read_bytes())
        else:
            slide_texts = []
        num_slides_hint = len(slide_texts) or 6
        demo_audio = _load_demo_audio_files(num_slides_hint)
        logger.info("TIMING [{}] load audio: {} files in {}", job_uuid[:8], len(demo_audio), _elapsed(t0))

        if not demo_audio:
            raise RuntimeError("Keine Demo-MP3s gefunden. Lege slide_001.mp3 in backend/demo/slides/ ab.")

        num_slides = min(len(slide_images_b64), len(demo_audio))
        if num_slides == 0:
            raise RuntimeError("Keine Demo-Slides oder Audio")

        subtitle_data = _load_demo_subtitles()
        slide_pause = 0.5

        db.update_job_status(job_uuid, "running", progress={"step": "video", "total": num_slides})

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            t0 = time.time()
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
            logger.info("TIMING [{}] write tmp files in {}", job_uuid[:8], _elapsed(t0))

            t0 = time.time()
            clip_paths: list[Path] = [tmp / f"clip_{i:03d}.mp4" for i in range(num_slides)]

            def _render_clip(i: int) -> None:
                t_clip = time.time()
                _create_slide_video(slide_image_paths[i], audio_paths[i], clip_paths[i], pause=slide_pause)
                logger.info("TIMING [{}] clip {}/{} in {}", job_uuid[:8], i + 1, num_slides, _elapsed(t_clip))

            db.update_job_status(job_uuid, "running", progress={"step": "video", "current": 0, "total": num_slides})
            with ThreadPoolExecutor(max_workers=max(1, os.cpu_count() // 2)) as executor:
                futures = {executor.submit(_render_clip, i): i for i in range(num_slides)}
                completed = 0
                for future in as_completed(futures):
                    future.result()
                    completed += 1
                    db.update_job_status(job_uuid, "running", progress={"step": "video", "current": completed, "total": num_slides})
            logger.info("TIMING [{}] all clips in {}", job_uuid[:8], _elapsed(t0))

            t0 = time.time()
            db.update_job_status(job_uuid, "running", progress={"step": "concat"})
            concat_path = tmp / "concat.mp4"
            _concatenate_videos(clip_paths, concat_path)
            logger.info("TIMING [{}] concat in {}", job_uuid[:8], _elapsed(t0))

            # Build subtitles from durations
            per_slide_data = [{"alignment": None, "audio_duration": _get_audio_duration(ap)} for ap in audio_paths]
            built_subs = build_subtitles(per_slide_data, slide_pause=slide_pause)

            final_subs = {
                "srt": subtitle_data.get("srt") or built_subs.get("srt", ""),
                "vtt": subtitle_data.get("vtt") or built_subs.get("vtt", ""),
                "txt": subtitle_data.get("txt") or built_subs.get("txt", ""),
                "alignment_json": built_subs.get("alignment_json", "[]"),
            }

            srt_content = final_subs.get("srt", "")
            if srt_content:
                t0 = time.time()
                db.update_job_status(job_uuid, "running", progress={"step": "subtitles"})
                srt_path = tmp / "subtitles.srt"
                srt_path.write_text(srt_content, encoding="utf-8")
                subtitled_path = tmp / "concat_sub.mp4"
                if _embed_subs(concat_path, srt_path, subtitled_path):
                    concat_path = subtitled_path
                logger.info("TIMING [{}] subtitles in {}", job_uuid[:8], _elapsed(t0))

            t0 = time.time()
            final_path = tmp / "final.mp4"
            output_bytes = _apply_faststart(concat_path, final_path)
            logger.info("TIMING [{}] faststart in {}", job_uuid[:8], _elapsed(t0))

            t0 = time.time()
            audio_bytes_list = [ap.read_bytes() for ap in audio_paths[:num_slides]]
            save_audio_cache(job_uuid, audio_bytes_list)

            result_path = save_result_file(job_uuid, ".mp4", output_bytes)
            logger.info("TIMING [{}] save result in {}", job_uuid[:8], _elapsed(t0))

            meta = {
                "subtitle_b64": base64.b64encode(
                    json.dumps(final_subs).encode("utf-8")
                ).decode("ascii"),
                "audio_id": job_uuid,
                "audio_count": num_slides,
            }
            save_result_meta(job_uuid, meta)

            # Save subtitle files separately
            for ext, fname in (("srt", "subtitles.srt"), ("vtt", "subtitles.vtt"), ("txt", "transcript.txt")):
                content = final_subs.get(ext, "")
                if content:
                    save_job_file(job_uuid, fname, content.encode("utf-8"))

        save_result_and_evict(job_uuid, result_path, "demo_screencast.mp4")
        db.update_job_status(job_uuid, "success")

        logger.info("TIMING [{}] TOTAL: {}", job_uuid[:8], _elapsed())
        logger.info("Demo render task {} completed", job_uuid)

    except Exception as e:
        logger.error("Demo render task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


async def _generate_all_scripts_async(slide_texts, kisski_client, glossary=None):
    """Async wrapper for batch script generation (called via asyncio.run)."""
    return kisski_client.generate_scripts_batch(slide_texts, None, glossary)
