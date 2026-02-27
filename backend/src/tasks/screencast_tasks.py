"""Celery tasks: Screencast auto, translate, render (+ demo render)."""

import asyncio
import json
import tempfile
import uuid
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import save_result_file, save_result_json, save_audio_cache


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_screencast_helpers():
    """Import screencast helpers lazily to avoid circular imports."""
    from src.routes.screencast import (
        PPTX_TMP_DIR,
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
        _save_pptx_tmp,
    )
    from src.services.subtitle_converter import build_subtitles
    return (
        PPTX_TMP_DIR, IMAGE_TMP_DIR,
        _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
        _create_slide_video, _concatenate_videos, _apply_faststart, _embed_subs,
        _get_audio_duration, _extract_text_per_slide, _save_pptx_tmp,
        build_subtitles,
    )


def _get_tts_client():
    from src.services.elevenlabs_client import ElevenLabsClient
    api_key = db.get_api_config_value("elevenlabs_api_key")
    if not api_key:
        raise RuntimeError("ElevenLabs API Key nicht konfiguriert")
    return ElevenLabsClient(api_key)


def _run_render_pipeline(
    job_uuid: str,
    file_id: str,
    scripts: list[str],
    voice_id: str,
    speed: float,
    slide_pause: float,
    embed_subtitles: bool,
    slide_images_override: list[Path] | None = None,
    dpi: int = 100,
) -> dict:
    """
    Core render pipeline shared by screencast_render and screencast_auto tasks.

    Returns a dict with:
      result_path, result_filename, audio_id, audio_count, subtitle_data
    """
    (
        PPTX_TMP_DIR, IMAGE_TMP_DIR,
        _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
        _create_slide_video, _concatenate_videos, _apply_faststart, _embed_subs,
        _get_audio_duration, _extract_text_per_slide, _save_pptx_tmp,
        build_subtitles,
    ) = _get_screencast_helpers()

    tts_client = _get_tts_client()

    db.update_job_status(job_uuid, "running", progress={"step": "images"})

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # ── Slide images ──────────────────────────────────────────────────
        if slide_images_override is not None:
            slide_images = slide_images_override
        else:
            prerendered_dir = IMAGE_TMP_DIR / file_id
            prerendered_images = sorted(prerendered_dir.glob("slide-*.png")) if prerendered_dir.exists() else []

            if prerendered_images and dpi == 100:
                logger.info("Render {}: using {} pre-rendered images (100 DPI)", job_uuid, len(prerendered_images))
                slide_images = prerendered_images
            else:
                pptx_src = PPTX_TMP_DIR / f"{file_id}.pptx"
                if not pptx_src.exists():
                    raise RuntimeError("PPTX nicht gefunden (abgelaufen oder ungültige ID). Bitte neu hochladen.")
                pptx_path = tmp / "translated.pptx"
                pptx_path.write_bytes(pptx_src.read_bytes())
                img_dir = tmp / "images"
                img_dir.mkdir()
                slide_images = asyncio.run(_convert_slides_to_images_async(pptx_path, img_dir, dpi))

        # ── TTS ───────────────────────────────────────────────────────────
        db.update_job_status(job_uuid, "running", progress={"step": "tts", "current": 0, "total": len(scripts)})
        tts_results = asyncio.run(_generate_all_tts(scripts, tts_client, tmp, speed, voice_id))
        audio_paths = [r[0] for r in tts_results]
        alignments = [r[1] for r in tts_results]

        num_slides = min(len(slide_images), len(audio_paths))
        if num_slides == 0:
            raise RuntimeError("Keine Slides verarbeitet")

        # ── Video clips ───────────────────────────────────────────────────
        db.update_job_status(job_uuid, "running", progress={"step": "video", "current": 0, "total": num_slides})
        clip_paths: list[Path] = []
        for i in range(num_slides):
            clip_path = tmp / f"clip_{i:03d}.mp4"
            _create_slide_video(slide_images[i], audio_paths[i], clip_path, pause=slide_pause, crf=23)
            clip_paths.append(clip_path)
            db.update_job_status(job_uuid, "running", progress={"step": "video", "current": i + 1, "total": num_slides})

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

        # ── Save audio cache (file-based, shared volume) ──────────────────
        audio_id = uuid.uuid4().hex
        audio_bytes_list = [ap.read_bytes() if ap is not None and ap.exists() else b"" for ap in audio_paths[:num_slides]]
        save_audio_cache(audio_id, audio_bytes_list)

        # ── Save result ───────────────────────────────────────────────────
        result_path = save_result_file(job_uuid, ".mp4", output_bytes)

        # Save meta (subtitles + audio info) alongside result
        meta = {
            "subtitle_b64": __import__("base64").b64encode(
                json.dumps(subtitle_data).encode("utf-8")
            ).decode("ascii"),
            "audio_id": audio_id,
            "audio_count": num_slides,
            "file_id": file_id,
        }
        meta_path = Path(result_path).with_suffix(".meta.json")
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

    # Clean up pre-rendered images after successful render
    prerendered_dir = IMAGE_TMP_DIR / file_id
    if prerendered_dir.exists():
        import shutil
        shutil.rmtree(prerendered_dir, ignore_errors=True)

    return {
        "result_path": result_path,
        "audio_id": audio_id,
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
    """Translate PPTX DE→EN, extract slide texts, optionally render slide images."""
    try:
        db.update_job_status(job_uuid, "running", progress={"step": "translate"})

        pptx_bytes = Path(input_path).read_bytes()

        from src.routes.translate import translate_pptx_content
        translated_bytes = translate_pptx_content(pptx_bytes, filename, glossary_json)

        (
            PPTX_TMP_DIR, IMAGE_TMP_DIR,
            _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
            _create_slide_video, _concatenate_videos, _apply_faststart, _embed_subs,
            _get_audio_duration, _extract_text_per_slide, _save_pptx_tmp,
            build_subtitles,
        ) = _get_screencast_helpers()

        db.update_job_status(job_uuid, "running", progress={"step": "extract"})
        slide_texts = _extract_text_per_slide(translated_bytes)
        if not slide_texts:
            raise ValueError("Keine Slides in der Präsentation gefunden")

        # Save translated PPTX to shared temp storage
        file_id = _save_pptx_tmp(translated_bytes)

        if fast_mode:
            result = {
                "slide_count": len(slide_texts),
                "slide_texts": slide_texts,
                "slide_images": [],
                "file_id": file_id,
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
                "file_id": file_id,
            }

        result_path = save_result_json(job_uuid, result)
        db.update_job_result(job_uuid, result_path, f"{Path(filename).stem}_translate.json")
        db.update_job_status(job_uuid, "success")

        # Clean up input file
        Path(input_path).unlink(missing_ok=True)

        logger.info("Screencast translate task {} completed: {} slides", job_uuid, len(slide_texts))

    except Exception as e:
        logger.error("Screencast translate task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


@celery_app.task(bind=True, name="screencast.render", queue="screencast")
def run_screencast_render(
    self,
    job_uuid: str,
    file_id: str,
    scripts: list[str],
    voice_id: str,
    speed: float,
    slide_pause: float,
    embed_subtitles: bool,
    original_filename: str = "screencast",
    dpi: int = 100,
):
    """Render final MP4 from edited scripts and stored PPTX."""
    try:
        result = _run_render_pipeline(
            job_uuid=job_uuid,
            file_id=file_id,
            scripts=scripts,
            voice_id=voice_id,
            speed=speed,
            slide_pause=slide_pause,
            embed_subtitles=embed_subtitles,
            dpi=dpi,
        )

        stem = Path(original_filename).stem if original_filename else "screencast"
        result_filename = f"{stem}_screencast_EN.mp4"
        db.update_job_result(job_uuid, result["result_path"], result_filename)
        db.update_job_status(job_uuid, "success")

        logger.info("Screencast render task {} completed", job_uuid)

    except Exception as e:
        logger.error("Screencast render task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
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
):
    """Full auto pipeline: translate → scripts → TTS → render."""
    try:
        db.update_job_status(job_uuid, "running", progress={"step": "translate"})

        pptx_bytes = Path(input_path).read_bytes()

        from src.routes.translate import translate_pptx_content
        translated_bytes = translate_pptx_content(pptx_bytes, filename, glossary_json)

        (
            PPTX_TMP_DIR, IMAGE_TMP_DIR,
            _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
            _create_slide_video, _concatenate_videos, _apply_faststart, _embed_subs,
            _get_audio_duration, _extract_text_per_slide, _save_pptx_tmp,
            build_subtitles,
        ) = _get_screencast_helpers()

        db.update_job_status(job_uuid, "running", progress={"step": "extract"})
        slide_texts = _extract_text_per_slide(translated_bytes)
        if not slide_texts:
            raise ValueError("Keine Slides in der Präsentation gefunden")

        file_id = _save_pptx_tmp(translated_bytes)

        # Generate scripts via KISSKI
        db.update_job_status(job_uuid, "running", progress={"step": "scripts", "total": len(slide_texts)})
        from src.services.kisski_client import KisskiClient
        kisski_api_key = db.get_api_config_value("kisski_api_key")
        if not kisski_api_key:
            raise RuntimeError("KISSKI API Key nicht konfiguriert")
        kisski_client = KisskiClient(
            api_key=kisski_api_key,
            base_url=db.get_api_config_value("kisski_base_url") or "https://chat-ai.academiccloud.de/v1",
            model=db.get_default_kisski_model() or "qwen3-30b-a3b-instruct-2507",
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
            file_id=file_id,
            scripts=scripts,
            voice_id=voice_id,
            speed=speed,
            slide_pause=0.5,
            embed_subtitles=True,
        )

        stem = Path(filename).stem
        result_filename = f"{stem}_screencast_EN.mp4"
        db.update_job_result(job_uuid, result["result_path"], result_filename)
        db.update_job_status(job_uuid, "success")

        # Clean up input file
        Path(input_path).unlink(missing_ok=True)

        logger.info("Screencast auto task {} completed: {}", job_uuid, result_filename)

    except Exception as e:
        logger.error("Screencast auto task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


@celery_app.task(bind=True, name="screencast.demo_render", queue="screencast")
def run_screencast_demo_render(
    self,
    job_uuid: str,
    file_id: str,
    dpi: int = 100,
):
    """Demo render: FFmpeg pipeline with pre-existing demo audio files."""
    import time
    t_start = time.time()

    def _elapsed(since=None):
        return f"{time.time() - (since or t_start):.2f}s"

    try:
        db.update_job_status(job_uuid, "running", progress={"step": "images"})

        from src.routes.screencast import (
            PPTX_TMP_DIR,
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

        # Get slide images
        import base64
        t0 = time.time()
        prerendered_dir = IMAGE_TMP_DIR / file_id if file_id else None
        prerendered_images = sorted(prerendered_dir.glob("slide-*.png")) if prerendered_dir and prerendered_dir.exists() else []

        if prerendered_images and dpi == 100:
            slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in prerendered_images]
            logger.info("TIMING [{}] images: pre-rendered 100dpi ({} slides) in {}", job_uuid[:8], len(slide_images_b64), _elapsed(t0))
        elif file_id and (PPTX_TMP_DIR / f"{file_id}.pptx").exists():
            pptx_src = PPTX_TMP_DIR / f"{file_id}.pptx"
            with tempfile.TemporaryDirectory() as tmpdir_img:
                img_dir = Path(tmpdir_img) / "images"
                img_dir.mkdir()
                pptx_copy = Path(tmpdir_img) / "render.pptx"
                pptx_copy.write_bytes(pptx_src.read_bytes())
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
            clip_paths: list[Path] = []
            for i in range(num_slides):
                t_clip = time.time()
                clip_path = tmp / f"clip_{i:03d}.mp4"
                _create_slide_video(slide_image_paths[i], audio_paths[i], clip_path, pause=slide_pause)
                clip_paths.append(clip_path)
                db.update_job_status(job_uuid, "running", progress={"step": "video", "current": i + 1, "total": num_slides})
                logger.info("TIMING [{}] clip {}/{} in {}", job_uuid[:8], i + 1, num_slides, _elapsed(t_clip))
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
            audio_id = uuid.uuid4().hex
            audio_bytes_list = [ap.read_bytes() for ap in audio_paths[:num_slides]]
            save_audio_cache(audio_id, audio_bytes_list)

            result_path = save_result_file(job_uuid, ".mp4", output_bytes)
            logger.info("TIMING [{}] save result in {}", job_uuid[:8], _elapsed(t0))

            meta = {
                "subtitle_b64": base64.b64encode(
                    json.dumps(final_subs).encode("utf-8")
                ).decode("ascii"),
                "audio_id": audio_id,
                "audio_count": num_slides,
                "file_id": file_id,
            }
            Path(result_path).with_suffix(".meta.json").write_text(json.dumps(meta), encoding="utf-8")

        db.update_job_result(job_uuid, result_path, "demo_screencast.mp4")
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
