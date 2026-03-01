"""Screencast route: translate DE PPTX → EN, extract text per slide, TTS, slide images, FFmpeg → MP4."""

import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pydantic import BaseModel

from src.dependencies import get_deepl_client, get_elevenlabs_client, get_kisski_client, get_current_user
from src.services.elevenlabs_client import ElevenLabsClient
from src.services.kisski_client import KisskiClient
from src.services.glossary import GlossaryService
from src.services.subtitle_converter import build_subtitles
from src.services.translation import TranslationService
from src.routes.translate import translate_pptx_content
from src.utils.file_validation import (
    MAX_OUTPUT_VIDEO_BYTES,
    MAX_SCREENCAST_SLIDES,
    MAX_UPLOAD_BYTES,
    SCREENCAST_EXTENSIONS,
)
from src import database as db
from src.storage import save_queue_file, save_audio_cache, get_audio_slide, get_audio_slide_count, load_result_json, save_result_json

router = APIRouter(tags=["screencast"])

# ── Temporary file storage (shared volume — accessible by celery-worker) ─────
PPTX_TMP_DIR = Path("/app/storage/screencast_tmp")
IMAGE_TMP_DIR = Path("/app/storage/screencast_tmp/images")

_cleanup_task: asyncio.Task | None = None


async def _cleanup_old_pptx_files() -> None:
    """Periodically delete PPTX temp files and pre-rendered image dirs older than 1 hour."""
    while True:
        await asyncio.sleep(300)  # check every 5 minutes
        try:
            cutoff = time.time() - 3600
            if PPTX_TMP_DIR.exists():
                for f in PPTX_TMP_DIR.glob("*.pptx"):
                    try:
                        if f.stat().st_mtime < cutoff:
                            f.unlink(missing_ok=True)
                            logger.info("Cleanup: deleted expired PPTX {}", f.name)
                    except OSError:
                        pass
            if IMAGE_TMP_DIR.exists():
                for d in IMAGE_TMP_DIR.iterdir():
                    if d.is_dir():
                        try:
                            if d.stat().st_mtime < cutoff:
                                shutil.rmtree(d, ignore_errors=True)
                                logger.info("Cleanup: deleted expired image dir {}", d.name)
                        except OSError:
                            pass
        except Exception as e:
            logger.warning("Cleanup error: {}", e)


def _maybe_start_cleanup_task() -> None:
    """Start the background cleanup task if not already running."""
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        try:
            _cleanup_task = asyncio.create_task(_cleanup_old_pptx_files())
        except RuntimeError:
            pass  # No running event loop yet


def _save_pptx_tmp(pptx_bytes: bytes) -> str:
    """Save PPTX bytes to PPTX_TMP_DIR/{uuid}.pptx and return the UUID."""
    PPTX_TMP_DIR.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    (PPTX_TMP_DIR / f"{file_id}.pptx").write_bytes(pptx_bytes)
    return file_id


# ── Pydantic models for step-by-step endpoints ──────────────────────────────

class ExtractTextsRequest(BaseModel):
    pptx_b64: str


class GenerateScriptsRequest(BaseModel):
    slide_texts: list[str]
    user_prompt: str | None = None
    glossary_json: str = ""


class PrepareRequest(BaseModel):
    translated_pptx_b64: str


class RenderRequest(BaseModel):
    scripts: list[str]
    file_id: str
    slide_images_b64: list[str] = []
    voice_id: str = ""
    speed: float = 0.9
    slide_pause: float = 0.5
    embed_subtitles: bool = True
    dpi: int = 100


class PrerenderRequest(BaseModel):
    file_id: str


class DemoRenderRequest(BaseModel):
    file_id: str = ""
    dpi: int = 100


class DemoTranslateRequest(BaseModel):
    fast_mode: bool = False


async def _prerender_images_task(file_id: str) -> None:
    """Background task: render slide images at 100 DPI and cache them in IMAGE_TMP_DIR."""
    pptx_src = PPTX_TMP_DIR / f"{file_id}.pptx"
    if not pptx_src.exists():
        logger.warning("Pre-render: PPTX not found for file_id={}", file_id)
        return
    out_dir = IMAGE_TMP_DIR / file_id
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        await asyncio.to_thread(_pptx_to_images, pptx_src, out_dir, 100)
        logger.info("Pre-rendering complete for file_id={}", file_id)
    except Exception as e:
        logger.warning("Pre-rendering failed for file_id={}: {}", file_id, e)


# ── Shared helpers ───────────────────────────────────────────────────────────

def _validate_upload(filename: str | None) -> str:
    if not filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")
    ext = Path(filename).suffix.lower()
    if ext not in SCREENCAST_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Nur .pptx erlaubt")
    return ext


def _build_service(glossary_json: str = "") -> TranslationService:
    client = get_deepl_client()
    if client is None:
        raise HTTPException(status_code=500, detail="DeepL API Key fehlt")
    glossary = GlossaryService()
    if glossary_json:
        try:
            entries = json.loads(glossary_json)
            if isinstance(entries, dict):
                glossary.set_entries(entries)
        except (json.JSONDecodeError, TypeError):
            pass
    return TranslationService(deepl_client=client, glossary=glossary)



def _extract_text_per_slide(pptx_bytes: bytes) -> list[str]:
    """Extract text from each slide of a PPTX, returning a list of strings (one per slide)."""
    prs = Presentation(BytesIO(pptx_bytes))
    slide_texts: list[str] = []
    for slide in prs.slides:
        texts: list[str] = []
        for shape in slide.shapes:
            _collect_shape_text(shape, texts)
        slide_texts.append("\n".join(texts))
    return slide_texts


def _collect_shape_text(shape, texts: list[str]) -> None:
    if shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            text = paragraph.text.strip()
            if text:
                texts.append(text)
    if shape.has_table:
        for row in shape.table.rows:
            for cell in row.cells:
                for paragraph in cell.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        texts.append(text)
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for subshape in shape.shapes:
            _collect_shape_text(subshape, texts)


def _apply_autofit_for_rendering(pptx_path: Path) -> Path:
    """Return a temp copy of the PPTX with AutoFit text shrunk by 20%.
    Works at XML level so inherited/theme font sizes are also captured.
    The original file is never modified."""
    prs = Presentation(str(pptx_path))
    changed = False
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            tf = shape.text_frame
            body_pr = tf._txBody.find(qn('a:bodyPr'))
            if body_pr is None:
                continue
            has_autofit = (
                body_pr.find(qn('a:normAutofit')) is not None or
                body_pr.find(qn('a:spAutoFit')) is not None
            )
            if not has_autofit:
                continue
            # Work directly on XML — shrink sz on all <a:rPr> elements
            for r_pr in tf._txBody.iter(qn('a:rPr')):
                sz = r_pr.get('sz')
                if sz:
                    r_pr.set('sz', str(int(int(sz) * 0.80)))
                else:
                    # No explicit size — set one based on default 1800 (18pt)
                    r_pr.set('sz', str(int(1800 * 0.80)))
                changed = True
            # Also shrink defRPr inside <a:pPr> (paragraph-level default)
            for p_pr in tf._txBody.iter(qn('a:pPr')):
                def_r_pr = p_pr.find(qn('a:defRPr'))
                if def_r_pr is not None:
                    sz = def_r_pr.get('sz')
                    if sz:
                        def_r_pr.set('sz', str(int(int(sz) * 0.80)))
                        changed = True

    render_path = pptx_path.parent / f"_render_{pptx_path.name}"
    prs.save(str(render_path))
    logger.info("AutoFit XML-level applied: changed={}", changed)
    return render_path


def _pptx_to_images(pptx_path: Path, output_dir: Path, dpi: int = 100) -> list[Path]:
    """Convert PPTX slides to PNG images using LibreOffice."""
    # Read actual slide dimensions so we can detect non-standard sizes and
    # pass the correct aspect ratio to the post-processing step.
    prs = Presentation(str(pptx_path))
    slide_width = prs.slide_width   # EMU (1 cm = 360000 EMU)
    slide_height = prs.slide_height
    width_cm = slide_width / 360000
    height_cm = slide_height / 360000
    slide_ratio = slide_width / slide_height
    logger.info("PPTX slide size: {:.2f}x{:.2f} cm (ratio {:.4f})", width_cm, height_cm, slide_ratio)

    render_pptx = _apply_autofit_for_rendering(pptx_path)

    cmd = [
        "libreoffice", "--headless", "--norestore",
        "--convert-to", "pdf",
        "--outdir", str(output_dir), str(render_pptx),
    ]
    logger.info("Converting PPTX to PDF: {}", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    pdf_path = output_dir / f"{render_pptx.stem}.pdf"
    if not pdf_path.exists():
        # PDF was not created — this is a real failure regardless of exit code
        logger.error("LibreOffice conversion failed (rc={}): {}", result.returncode, result.stderr[:300])
        raise RuntimeError(f"LibreOffice Konvertierung fehlgeschlagen: {result.stderr[:200]}")
    if result.returncode != 0:
        # PDF exists despite non-zero exit — treat javaldx / Java warnings as non-fatal
        logger.warning("LibreOffice exited with rc={} but PDF was created (non-fatal): {}", result.returncode, result.stderr[:200])

    # Convert PDF pages to individual PNG images using pdftoppm (poppler-utils).
    slide_prefix = str(output_dir / "slide")
    cmd = [
        "pdftoppm", "-png", "-r", str(dpi),
        str(pdf_path), slide_prefix,
    ]
    logger.info("Converting PDF to images: {}", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.error("PDF to image conversion failed: {}", result.stderr[:300])
        raise RuntimeError(f"PDF zu Bild Konvertierung fehlgeschlagen: {result.stderr[:200]}")

    # Collect generated images (pdftoppm names them slide-1.png, slide-2.png, ...)
    images = sorted(output_dir.glob("slide-*.png"))
    if not images:
        raise RuntimeError("Keine Slide-Bilder erstellt")

    logger.info("Generated {} slide images", len(images))
    logger.info("Slide image sizes: {}", [(p.name, p.stat().st_size) for p in images[:3]])

    with Image.open(images[0]) as img:
        logger.info("First slide dimensions: {}x{} px (ratio {:.4f})", img.width, img.height, img.width / img.height)

    return images


def _get_audio_duration(audio_path: Path | None) -> float:
    """Get the exact duration of an audio file in seconds using ffprobe.

    Returns 3.0 for silent slides (audio_path is None).
    """
    if audio_path is None:
        return 3.0
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe fehlgeschlagen: {result.stderr[:200]}")
    return float(result.stdout.strip())


def _create_slide_video(image_path: Path, audio_path: Path | None, output_path: Path, pause: float = 0.0, crf: int = 23) -> None:
    """Combine a single slide image with its audio into a video clip.

    If audio_path is None (silent/empty slide), produces a video-only clip
    with a fixed 3-second duration and no audio track.
    """
    # Normalise: treat missing or empty audio files the same as None (silent slide)
    if audio_path is not None and (not audio_path.exists() or audio_path.stat().st_size == 0):
        logger.warning("Audio file is empty/missing ({}), falling back to silent slide", audio_path)
        audio_path = None

    logger.info(
        "Creating clip {}: image={} ({}b), audio={} ({}b)",
        output_path.name,
        image_path,
        image_path.stat().st_size if image_path.exists() else "MISSING",
        audio_path,
        audio_path.stat().st_size if audio_path and audio_path.exists() else "MISSING/None",
    )
    with Image.open(image_path) as img:
        logger.info("Image dimensions: {}x{}", img.width, img.height)
    if audio_path is None:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "3",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
            "-threads", "2",
            "-crf", str(crf),
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error("Slide video creation failed (rc={}):\nSTDOUT: {}\nSTDERR: {}", result.returncode, result.stdout[-500:], result.stderr[-500:])
            raise RuntimeError(f"Video-Erstellung fehlgeschlagen (kein Audio): {result.stderr[-300:]}")
        return

    duration = _get_audio_duration(audio_path)

    if pause > 0:
        # Create silent audio segment
        silence_path = output_path.with_suffix(".silence.mp3")
        cmd_silence = [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"anullsrc=r=44100:cl=mono",
            "-t", str(pause),
            "-c:a", "libmp3lame", str(silence_path),
        ]
        subprocess.run(cmd_silence, capture_output=True, text=True, timeout=30)

        # Concatenate TTS audio + silence
        audio_with_pause_path = output_path.with_suffix(".paused.mp3")
        concat_audio_file = output_path.with_suffix(".audiolist.txt")
        with open(concat_audio_file, "w") as f:
            f.write(f"file '{audio_path}'\n")
            f.write(f"file '{silence_path}'\n")
        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_audio_file),
            "-c", "copy", str(audio_with_pause_path),
        ]
        subprocess.run(cmd_concat, capture_output=True, text=True, timeout=30)
        final_audio = audio_with_pause_path
        total_duration = duration + pause
    else:
        final_audio = audio_path
        total_duration = duration

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(final_audio),
        "-t", str(total_duration),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
        "-threads", "2",
        "-c:a", "aac", "-b:a", "192k",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error("Slide video creation failed (rc={}):\nSTDOUT: {}\nSTDERR: {}", result.returncode, result.stdout[-500:], result.stderr[-500:])
        raise RuntimeError(f"Video-Erstellung fehlgeschlagen: {result.stderr[-300:]}")


def _concatenate_videos(video_paths: list[Path], output_path: Path) -> None:
    """Concatenate multiple video clips into one MP4."""
    concat_file = output_path.parent / "concat_list.txt"
    with open(concat_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error("Video concatenation failed: {}", result.stderr[:300])
        raise RuntimeError(f"Video-Zusammenführung fehlgeschlagen: {result.stderr[:200]}")


def _probe_streams(file_path: Path) -> str:
    """Return a short summary of streams in a media file via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_type,codec_name",
        "-of", "csv=p=0",
        str(file_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return result.stdout.strip() if result.returncode == 0 else f"(ffprobe error: {result.stderr[:100]})"


def _apply_faststart(input_path: Path, output_path: Path) -> bytes:
    """Apply faststart to MP4 for web streaming."""
    logger.info("faststart input streams: {}", _probe_streams(input_path))
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-map", "0",
        "-c", "copy", "-movflags", "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.warning("faststart fix failed (rc={}): {}", result.returncode, result.stderr[:300])
        return input_path.read_bytes()
    logger.info("faststart output streams: {}", _probe_streams(output_path))
    return output_path.read_bytes()


def _embed_subtitles(video_path: Path, sub_path: Path, output_path: Path) -> bool:
    """Mux a subtitle file (SRT) as a soft-subtitle track into an MP4.

    Uses mov_text codec so the subtitle track can be toggled on/off in players.
    Returns True on success, False on failure (non-fatal).
    """
    sub_size = sub_path.stat().st_size if sub_path.exists() else 0
    logger.info("Embedding soft subtitles: sub_file={}, size={} bytes", sub_path.name, sub_size)
    if sub_size == 0:
        logger.warning("Subtitle file is empty, skipping embedding")
        return False

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-sub_charenc", "UTF-8",
        "-f", "srt",
        "-i", str(sub_path),
        "-map", "0:v", "-map", "0:a", "-map", "1:s",
        "-c:v", "copy", "-c:a", "copy",
        "-c:s", "mov_text",
        "-metadata:s:s:0", "language=eng",
        "-metadata:s:s:0", "handler_name=English",
        str(output_path),
    ]
    logger.info("FFmpeg soft-sub cmd: {}", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.error("Subtitle embedding FAILED (rc={}): {}", result.returncode, result.stderr[:500])
        return False

    out_size = output_path.stat().st_size if output_path.exists() else 0
    logger.info("Soft subtitles embedded, output={} bytes, streams: {}",
                out_size, _probe_streams(output_path))
    return True


async def _generate_all_scripts(
    slide_texts: list[str],
    kisski_client: KisskiClient,
    user_prompt: str | None = None,
    glossary: dict | None = None,
) -> list[str]:
    """Generate spoken scripts for all slides in a single KISSKI call."""
    try:
        scripts = await asyncio.to_thread(
            kisski_client.generate_scripts_batch, slide_texts, user_prompt, glossary
        )
        logger.info("Batch script generation completed for {} slides", len(slide_texts))
        return scripts
    except RuntimeError as e:
        logger.error("Batch script generation failed: {}", e)
        raise HTTPException(
            status_code=502,
            detail=f"Skript-Generierung fehlgeschlagen: {e}",
        )


# PARALLELIZED
async def _generate_all_tts(
    slide_scripts: list[str],
    tts_client: ElevenLabsClient,
    tmp: Path,
    speed: float,
    voice_id: str = "",
    on_slide_done: Callable[[int, int], None] | None = None,
) -> list[tuple[Path, dict | None]]:
    """Generate TTS audio for all slides in parallel via ElevenLabs.

    Returns a list of (audio_path, alignment_or_None) tuples.
    on_slide_done(current, total) is called after each slide completes.
    """
    sem = asyncio.Semaphore(10)
    lock = asyncio.Lock()
    counter = 0
    total = len(slide_scripts)
    audio_paths: list[Path | None] = [tmp / f"slide_{i:03d}.mp3" for i in range(total)]
    alignments: list[dict | None] = [None] * total

    async def _tts(i: int, script_text: str) -> None:
        nonlocal counter
        if not script_text.strip():
            # Empty slide: no audio file — _create_slide_video handles None as video-only
            audio_paths[i] = None
            logger.info("Slide {}/{}: empty script, audio_path set to None", i + 1, total)
        else:
            async with sem:
                try:
                    result = await asyncio.to_thread(
                        tts_client.synthesize_with_timestamps,
                        script_text, "EN", voice_id=voice_id, speed=speed,
                    )
                    audio_paths[i].write_bytes(result["audio_bytes"])
                    alignments[i] = result["alignment"]
                    logger.info("TTS for slide {}/{} done", i + 1, total)
                except Exception as e:
                    logger.error("TTS failed for slide {}: {}", i + 1, e)
                    raise HTTPException(
                        status_code=502,
                        detail=f"TTS-Fehler bei Folie {i + 1}: {e}",
                    )
        async with lock:
            counter += 1
            if on_slide_done:
                on_slide_done(counter, total)

    await asyncio.gather(*[_tts(i, t) for i, t in enumerate(slide_scripts)])
    return list(zip(audio_paths, alignments))


# PARALLELIZED
async def _convert_slides_to_images_async(
    pptx_path: Path, img_dir: Path, dpi: int = 100
) -> list[Path]:
    """Run LibreOffice image conversion in a thread."""
    return await asyncio.to_thread(_pptx_to_images, pptx_path, img_dir, dpi)


# ── Auto-mode endpoint (unchanged) ──────────────────────────────────────────

@router.post("/screencast")
async def screencast(
    request: Request,
    file: UploadFile = File(...),
    voice_id: str = Form(""),
    speed: float = Form(0.9),
    glossary_json: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """Queue a screencast job: translate DE PPTX → EN, generate scripts, TTS, render MP4."""
    _validate_upload(file.filename)

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    pptx_bytes = await file.read()
    if not pptx_bytes:
        raise HTTPException(status_code=400, detail="Datei ist leer")

    user_id = current_user.get("user_id", 0)
    _SCREENCAST_TOOLS = ["screencast_translate", "screencast_render", "screencast_auto", "screencast_demo_render"]
    if db.has_active_job_for_tool(user_id, _SCREENCAST_TOOLS):
        raise HTTPException(status_code=409, detail="Du hast bereits einen laufenden Screencast-Job.")

    job_uuid = uuid.uuid4().hex
    input_path = save_queue_file(job_uuid, ".pptx", pptx_bytes)
    db.create_job(job_uuid, user_id, "screencast_auto", file.filename or "screencast.pptx", input_path)

    from src.tasks.screencast_tasks import run_screencast_auto
    task = run_screencast_auto.apply_async(args=[
        job_uuid,
        input_path,
        file.filename or "screencast.pptx",
        voice_id,
        speed,
        glossary_json,
    ])
    db.set_job_celery_task_id(job_uuid, task.id)

    logger.info("Screencast auto job queued: job_uuid={}, file={}", job_uuid, file.filename)
    return {"job_uuid": job_uuid}


# ── Step-by-step endpoints ───────────────────────────────────────────────────

@router.post("/screencast/translate")
async def screencast_translate(
    request: Request,
    file: UploadFile = File(...),
    glossary_json: str = Form(""),
    fast_mode: bool = Form(False),
    current_user: dict = Depends(get_current_user),
):
    """Queue a translate job: translate PPTX DE→EN, extract slide texts (+ images)."""
    _validate_upload(file.filename)
    _maybe_start_cleanup_task()

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    pptx_bytes = await file.read()
    if not pptx_bytes:
        raise HTTPException(status_code=400, detail="Datei ist leer")

    user_id = current_user.get("user_id", 0)
    _SCREENCAST_TOOLS = ["screencast_translate", "screencast_render", "screencast_auto", "screencast_demo_render"]
    if db.has_active_job_for_tool(user_id, _SCREENCAST_TOOLS):
        raise HTTPException(status_code=409, detail="Du hast bereits einen laufenden Screencast-Job.")

    job_uuid = uuid.uuid4().hex
    input_path = save_queue_file(job_uuid, ".pptx", pptx_bytes)
    db.create_job(job_uuid, user_id, "screencast_translate", file.filename or "screencast.pptx", input_path)

    from src.tasks.screencast_tasks import run_screencast_translate
    task = run_screencast_translate.apply_async(args=[
        job_uuid,
        input_path,
        file.filename or "screencast.pptx",
        glossary_json,
        fast_mode,
    ])
    db.set_job_celery_task_id(job_uuid, task.id)

    logger.info("Screencast translate job queued: job_uuid={}, file={}, fast_mode={}", job_uuid, file.filename, fast_mode)
    return {"job_uuid": job_uuid}


@router.post("/screencast/extract-texts")
async def screencast_extract_texts(body: ExtractTextsRequest):
    """Extract slide texts from a PPTX (base64-encoded)."""
    try:
        pptx_bytes = base64.b64decode(body.pptx_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültige PPTX-Daten (Base64)")

    logger.info("Screencast/extract-texts: extracting texts from PPTX")
    slide_texts = _extract_text_per_slide(pptx_bytes)
    if not slide_texts:
        raise HTTPException(status_code=400, detail="Keine Slides in der Präsentation gefunden")

    if len(slide_texts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(slide_texts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    return {
        "slide_count": len(slide_texts),
        "slide_texts": slide_texts,
    }


@router.post("/screencast/prepare")
async def screencast_prepare(body: PrepareRequest):
    """Convert translated PPTX to slide images."""
    try:
        pptx_bytes = base64.b64decode(body.translated_pptx_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültige PPTX-Daten (Base64)")

    logger.info("Screencast/prepare: converting PPTX to images")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        translated_pptx_path = tmp / "translated.pptx"
        translated_pptx_path.write_bytes(pptx_bytes)
        img_dir = tmp / "images"
        img_dir.mkdir()

        try:
            slide_image_paths = await _convert_slides_to_images_async(
                translated_pptx_path, img_dir
            )
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

        slide_images_b64: list[str] = []
        for img_path in slide_image_paths:
            slide_images_b64.append(base64.b64encode(img_path.read_bytes()).decode())

    return {
        "slide_images": slide_images_b64,
    }


@router.get("/screencast/file/{file_id}")
async def download_pptx_file(file_id: str):
    """Download translated PPTX from temp storage (file kept for render)."""
    if not re.match(r"^[a-f0-9]{32}$", file_id):
        raise HTTPException(status_code=400, detail="Ungültige file_id")
    pptx_path = PPTX_TMP_DIR / f"{file_id}.pptx"
    if not pptx_path.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden (abgelaufen oder ungültige ID)")
    data = pptx_path.read_bytes()
    logger.info("Serving PPTX file_id={} ({} bytes)", file_id, len(data))
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": 'attachment; filename="translated.pptx"',
        },
    )


@router.post("/screencast/upload-corrected")
async def screencast_upload_corrected(
    request: Request,
    file: UploadFile = File(...),
):
    """Upload a corrected PPTX, save to temp storage, extract texts and slide images."""
    _validate_upload(file.filename)
    _maybe_start_cleanup_task()

    pptx_bytes = await file.read()
    if not pptx_bytes:
        raise HTTPException(status_code=400, detail="Datei ist leer")

    logger.info("Screencast/upload-corrected: '{}' ({} bytes)", file.filename, len(pptx_bytes))

    slide_texts = _extract_text_per_slide(pptx_bytes)
    if not slide_texts:
        raise HTTPException(status_code=400, detail="Keine Slides in der Präsentation gefunden")

    if len(slide_texts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(slide_texts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    file_id = _save_pptx_tmp(pptx_bytes)
    logger.info("Saved corrected PPTX as file_id={}", file_id)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pptx_path = tmp / "corrected.pptx"
        pptx_path.write_bytes(pptx_bytes)
        img_dir = tmp / "images"
        img_dir.mkdir()
        try:
            slide_image_paths = await _convert_slides_to_images_async(pptx_path, img_dir)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in slide_image_paths]

    return {
        "file_id": file_id,
        "slide_texts": slide_texts,
        "slide_images": slide_images_b64,
    }


@router.post("/screencast/generate-scripts")
async def screencast_generate_scripts(body: GenerateScriptsRequest):
    """Generate spoken scripts for each slide via KISSKI LLM."""
    if not body.slide_texts:
        raise HTTPException(status_code=400, detail="Keine Folientexte übergeben")

    if len(body.slide_texts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(body.slide_texts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    logger.info(
        "Screencast/generate-scripts: {} slides, user_prompt={}",
        len(body.slide_texts),
        bool(body.user_prompt),
    )

    kisski_client = get_kisski_client()
    glossary_dict: dict | None = None
    if body.glossary_json:
        try:
            glossary_dict = json.loads(body.glossary_json)
        except (json.JSONDecodeError, TypeError):
            pass

    # PARALLELIZED
    scripts = await _generate_all_scripts(
        body.slide_texts, kisski_client, user_prompt=body.user_prompt, glossary=glossary_dict
    )

    return {"scripts": scripts}


@router.post("/screencast/prerender-images")
async def prerender_images(body: PrerenderRequest, background_tasks: BackgroundTasks):
    """Start background pre-rendering of slide images at 300 DPI.

    Call this after the user confirms scripts so images are ready when /render is called.
    Fire-and-forget: always returns immediately.
    """
    if not re.match(r"^[a-f0-9]{32}$", body.file_id):
        raise HTTPException(status_code=400, detail="Ungültige file_id")
    background_tasks.add_task(_prerender_images_task, body.file_id)
    logger.info("Pre-render started for file_id={}", body.file_id)
    return {"status": "started"}


@router.post("/screencast/render")
async def screencast_render(
    body: RenderRequest,
    current_user: dict = Depends(get_current_user),
):
    """Queue a render job: final MP4 from edited scripts and stored PPTX."""
    if not body.scripts:
        raise HTTPException(status_code=400, detail="Keine Skripte übergeben")

    if len(body.scripts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(body.scripts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    user_id = current_user.get("user_id", 0)
    # Only block if a render/auto job is already running (translate jobs are short and non-blocking)
    if db.has_active_job_for_tool(user_id, ["screencast_render", "screencast_auto", "screencast_demo_render"]):
        raise HTTPException(status_code=409, detail="Du hast bereits einen laufenden Screencast-Render-Job.")

    job_uuid = uuid.uuid4().hex
    db.create_job(job_uuid, user_id, "screencast_render", "screencast.pptx")

    from src.tasks.screencast_tasks import run_screencast_render
    task = run_screencast_render.apply_async(args=[
        job_uuid,
        body.file_id,
        body.scripts,
        body.voice_id,
        body.speed,
        body.slide_pause,
        body.embed_subtitles,
        "screencast.pptx",
        body.dpi,
    ])
    db.set_job_celery_task_id(job_uuid, task.id)

    logger.info("Screencast render job queued: job_uuid={}, file_id={}", job_uuid, body.file_id)
    return {"job_uuid": job_uuid}


# ── Audio download endpoint ──────────────────────────────────────────────────

@router.get("/screencast/audio/{audio_id}/{slide_index}")
async def download_slide_audio(audio_id: str, slide_index: int):
    """Download a single per-slide MP3 from the render audio cache (file-based)."""
    count = get_audio_slide_count(audio_id)
    if count == 0:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden (abgelaufen oder ungültige ID)")
    if slide_index < 0 or slide_index >= count:
        raise HTTPException(status_code=404, detail=f"Folie {slide_index + 1} nicht gefunden")

    audio_bytes = get_audio_slide(audio_id, slide_index)
    if audio_bytes is None:
        raise HTTPException(status_code=404, detail=f"Folie {slide_index + 1} nicht gefunden")

    filename = f"slide_{slide_index + 1:02d}.mp3"
    return StreamingResponse(
        iter([audio_bytes]),
        media_type="audio/mpeg",
        headers={
            "Content-Length": str(len(audio_bytes)),
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ── Demo-mode endpoints ──────────────────────────────────────────────────────

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo"  # /app/demo in Docker


def _load_demo_user_prompt() -> str:
    """Load user prompt from Anweisung.txt in demo/slides/."""
    prompt_path = DEMO_DIR / "slides" / "Anweisung.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return ""


def _load_demo_scripts() -> list[str]:
    """Extract per-slide scripts from the SRT file in demo/slides/.

    Detects slide boundaries by finding gaps > 0.3s between consecutive
    subtitle entries, then joins each group's text into one script string.
    """
    srt_path = DEMO_DIR / "slides" / "subtitles.srt"
    if not srt_path.exists():
        return []

    content = srt_path.read_text(encoding="utf-8")
    # Parse SRT entries: (start_seconds, end_seconds, text)
    entries: list[tuple[float, float, str]] = []
    for block in re.split(r"\n\n+", content.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        m = re.match(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", lines[1])
        if not m:
            continue
        start = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 1000
        end = int(m[5]) * 3600 + int(m[6]) * 60 + int(m[7]) + int(m[8]) / 1000
        text = " ".join(lines[2:]).strip()
        entries.append((start, end, text))

    if not entries:
        return []

    # Group entries into slides by detecting gaps > 0.3s
    slides: list[list[str]] = [[]]
    for i, (start, end, text) in enumerate(entries):
        if i > 0:
            prev_end = entries[i - 1][1]
            if start - prev_end > 0.3:
                slides.append([])
        slides[-1].append(text)

    return [" ".join(texts) for texts in slides]


def _find_demo_pptx() -> Path | None:
    """Find the first PPTX file in demo/slides/."""
    slides_dir = DEMO_DIR / "slides"
    if not slides_dir.exists():
        return None
    pptx_files = sorted(slides_dir.glob("*.pptx"))
    return pptx_files[0] if pptx_files else None


def _load_demo_slide_images() -> list[str]:
    """Load slide images from demo/slides/ as base64 strings.

    Falls back to generating placeholder images via FFmpeg if no PNGs exist.
    """
    slides_dir = DEMO_DIR / "slides"
    if not slides_dir.exists():
        return []
    images = sorted(slides_dir.glob("slide_*.png"))
    if not images:
        images = sorted(slides_dir.glob("*.png"))
    if images:
        return [base64.b64encode(img.read_bytes()).decode() for img in images]
    return []


_demo_images_cache: list[str] = []


async def _get_demo_slide_images(num_slides: int) -> list[str]:
    """Get demo slide images with PPTX extraction and caching.

    Priority: 1) PNGs in demo/slides/  2) cached PPTX extraction
    3) fresh PPTX extraction → cache in /tmp  4) placeholder generation
    """
    global _demo_images_cache

    # 1. Check for existing PNGs
    images = _load_demo_slide_images()
    if images:
        return images

    # 2. Return from cache if available
    if _demo_images_cache:
        logger.info("Using cached PPTX images ({} slides)", len(_demo_images_cache))
        return _demo_images_cache

    # 3. Try extracting from PPTX
    slides_dir = DEMO_DIR / "slides"
    pptx_files = sorted(slides_dir.glob("*.pptx")) if slides_dir.exists() else []
    if pptx_files:
        pptx_path = pptx_files[0]
        logger.info("Extracting images from PPTX: {}", pptx_path.name)
        pptx_bytes = pptx_path.read_bytes()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            tmp_pptx = tmp / "demo.pptx"
            tmp_pptx.write_bytes(pptx_bytes)
            img_dir = tmp / "images"
            img_dir.mkdir()
            try:
                image_paths = await _convert_slides_to_images_async(tmp_pptx, img_dir)
                _demo_images_cache = [
                    base64.b64encode(p.read_bytes()).decode() for p in image_paths
                ]
                logger.info("Extracted and cached {} images from PPTX", len(_demo_images_cache))
                return _demo_images_cache
            except RuntimeError as e:
                logger.warning("PPTX image extraction failed: {}", e)

    # 4. Fallback: generate placeholder slides from PPTX texts
    pptx_path = _find_demo_pptx()
    if pptx_path:
        slide_texts = _extract_text_per_slide(pptx_path.read_bytes())[:num_slides]
    else:
        slide_texts = [f"Slide {i+1}" for i in range(num_slides)]
    logger.info("Generating {} placeholder slides", len(slide_texts))
    return await asyncio.to_thread(_generate_placeholder_slides, slide_texts)


def _generate_placeholder_slides(slide_texts: list[str]) -> list[str]:
    """Generate simple placeholder slide images using FFmpeg drawtext.

    Returns list of base64-encoded PNGs.
    """
    colors = ["#1a365d", "#2d3748", "#1e3a5f", "#2c5282", "#2b6cb0", "#3182ce"]
    result: list[str] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for i, text in enumerate(slide_texts):
            out = tmp / f"slide_{i:03d}.png"
            title = text.split("\n")[0][:60]
            color = colors[i % len(colors)]
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c={color}:s=1280x720:d=1",
                "-vf", f"drawtext=text='{title}':fontcolor=white:fontsize=40"
                        f":x=(w-text_w)/2:y=(h-text_h)/2:font=DejaVu Sans",
                "-frames:v", "1",
                str(out),
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if out.exists():
                result.append(base64.b64encode(out.read_bytes()).decode())
    return result


def _get_demo_slide_images_sync(num_slides: int = 6) -> list[str]:
    """Synchronous version of _get_demo_slide_images for use in Celery tasks."""
    global _demo_images_cache

    images = _load_demo_slide_images()
    if images:
        return images

    if _demo_images_cache:
        return _demo_images_cache

    slides_dir = DEMO_DIR / "slides"
    pptx_files = sorted(slides_dir.glob("*.pptx")) if slides_dir.exists() else []
    if pptx_files:
        pptx_path = pptx_files[0]
        logger.info("Extracting images from PPTX (sync): {}", pptx_path.name)
        pptx_bytes = pptx_path.read_bytes()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            tmp_pptx = tmp / "demo.pptx"
            tmp_pptx.write_bytes(pptx_bytes)
            img_dir = tmp / "images"
            img_dir.mkdir()
            try:
                image_paths = _pptx_to_images(tmp_pptx, img_dir)
                _demo_images_cache = [
                    base64.b64encode(p.read_bytes()).decode() for p in image_paths
                ]
                logger.info("Extracted and cached {} images from PPTX (sync)", len(_demo_images_cache))
                return _demo_images_cache
            except RuntimeError as e:
                logger.warning("PPTX image extraction failed (sync): {}", e)

    pptx_path = _find_demo_pptx()
    if pptx_path:
        slide_texts_local = _extract_text_per_slide(pptx_path.read_bytes())[:num_slides]
    else:
        slide_texts_local = [f"Slide {i+1}" for i in range(num_slides)]
    return _generate_placeholder_slides(slide_texts_local)


def _load_demo_subtitles() -> dict:
    """Load subtitle data from files in demo/slides/ directory."""
    slides_dir = DEMO_DIR / "slides"
    subtitle_data: dict[str, str] = {
        "srt": "",
        "vtt": "",
        "txt": "",
        "alignment_json": "[]",
    }
    file_map = {
        "srt": "subtitles.srt",
        "vtt": "subtitles.vtt",
        "txt": "transcript.txt",
    }
    for key, filename in file_map.items():
        filepath = slides_dir / filename
        if filepath.exists():
            subtitle_data[key] = filepath.read_text(encoding="utf-8")
    # Generate plain text from scripts if transcript.txt doesn't exist
    if not subtitle_data["txt"]:
        scripts = _load_demo_scripts()
        if scripts:
            subtitle_data["txt"] = " ".join(scripts)
    return subtitle_data


@router.get("/screencast/demo-available")
async def demo_available():
    """Check whether demo data is available."""
    demo_enabled = db.get_setting("demo_data", "false").lower() == "true"
    pptx_exists = _find_demo_pptx() is not None
    video_exists = (DEMO_DIR / "video.mp4").exists()
    if not video_exists:
        for search_dir in [DEMO_DIR, DEMO_DIR / "slides"]:
            if search_dir.exists() and list(search_dir.glob("*.mp4")):
                video_exists = True
                break
    return {
        "available": demo_enabled and pptx_exists,
        "has_video": demo_enabled and video_exists,
        "demo_data_enabled": demo_enabled,
        "pptx_exists": pptx_exists,
        "video_exists": video_exists,
    }


@router.post("/screencast/demo/translate")
async def demo_translate(body: DemoTranslateRequest):
    """Return demo translation data (slide images, texts, translated PPTX).

    Requires a PPTX file in demo/slides/. Reads user prompt from Anweisung.txt.
    """
    global _demo_images_cache

    if db.get_setting("demo_data", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Demo-Modus ist nicht aktiviert")

    pptx_path = _find_demo_pptx()
    if not pptx_path:
        raise HTTPException(status_code=404, detail="Keine PPTX in demo/slides/ gefunden")

    user_prompt = _load_demo_user_prompt()
    _maybe_start_cleanup_task()

    logger.info("Demo/translate: using PPTX '{}', fast_mode={}", pptx_path.name, body.fast_mode)
    pptx_bytes = pptx_path.read_bytes()

    # Save to temp storage so file_id can be used for download/render
    file_id = _save_pptx_tmp(pptx_bytes)
    logger.info("Demo/translate: saved PPTX as file_id={}", file_id)

    # Extract slide texts
    slide_texts = _extract_text_per_slide(pptx_bytes)
    if not slide_texts:
        raise HTTPException(status_code=400, detail="Keine Slides in der Präsentation gefunden")

    if body.fast_mode:
        return {
            "slide_count": len(slide_texts),
            "slide_texts": slide_texts,
            "slide_images": [],
            "file_id": file_id,
            "user_prompt": user_prompt,
        }

    # Extract images via the same pipeline as screencast/translate (no placeholder fallback)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pptx_tmp_path = tmp / "demo.pptx"
        pptx_tmp_path.write_bytes(pptx_bytes)
        img_dir = tmp / "images"
        img_dir.mkdir()
        try:
            slide_image_paths = await _convert_slides_to_images_async(pptx_tmp_path, img_dir)
            slide_images_b64 = [
                base64.b64encode(p.read_bytes()).decode() for p in slide_image_paths
            ]
            # Keep cache in sync so demo_render uses the same images
            _demo_images_cache = slide_images_b64
            logger.info("Demo/translate: extracted {} slide images", len(slide_images_b64))
        except RuntimeError as e:
            logger.warning("Demo/translate: image extraction failed ({}), falling back to _get_demo_slide_images", e)
            slide_images_b64 = await _get_demo_slide_images(len(slide_texts))

    num = min(len(slide_images_b64), len(slide_texts))
    first_size = len(slide_images_b64[0]) if slide_images_b64 else 0
    logger.info("Demo/translate returning: slide_images count={}, first_size={}", num, first_size)
    return {
        "slide_count": num,
        "slide_texts": slide_texts[:num],
        "slide_images": slide_images_b64[:num],
        "file_id": file_id,
        "user_prompt": user_prompt,
    }


@router.post("/screencast/demo/generate-scripts")
async def demo_generate_scripts():
    """Return demo-generated scripts parsed from the SRT file."""
    if db.get_setting("demo_data", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Demo-Modus ist nicht aktiviert")

    scripts = _load_demo_scripts()
    if not scripts:
        raise HTTPException(status_code=404, detail="Keine Demo-Skripte (subtitles.srt fehlt in demo/slides/)")

    logger.info("Demo/generate-scripts: returning {} scripts", len(scripts))
    return {"scripts": scripts}


_demo_split_dir: Path | None = None


def _load_demo_audio_files(num_slides: int) -> list[Path]:
    """Load per-slide MP3 audio files from demo/slides/.

    If individual slide_*.mp3 files exist, return them directly.
    If only a single combined MP3 exists, split it into equal parts in /tmp.
    """
    global _demo_split_dir

    slides_dir = DEMO_DIR / "slides"
    if not slides_dir.exists():
        return []

    # Check demo/slides/ and demo/slides/Audio/ for per-slide MP3s
    for search_dir in [slides_dir, slides_dir / "Audio"]:
        per_slide = sorted(search_dir.glob("slide_*.mp3"))
        if per_slide:
            return per_slide

    # Check if we already split previously (cached in /tmp)
    if _demo_split_dir and _demo_split_dir.exists():
        cached = sorted(_demo_split_dir.glob("slide_*.mp3"))
        if len(cached) == num_slides:
            return cached

    # Look for any single MP3 to split
    all_mp3 = sorted(slides_dir.glob("*.mp3"))
    if not all_mp3 or num_slides < 1:
        return []

    combined_mp3 = all_mp3[0]
    logger.info("Demo: splitting combined MP3 '{}' into {} parts", combined_mp3.name, num_slides)

    # Get total duration
    dur_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(combined_mp3),
    ]
    dur_result = subprocess.run(dur_cmd, capture_output=True, text=True, timeout=15)
    if dur_result.returncode != 0:
        logger.error("Failed to probe MP3 duration: {}", dur_result.stderr[:200])
        return []
    total_duration = float(dur_result.stdout.strip())
    segment_duration = total_duration / num_slides

    # Split into /tmp (demo volume is read-only)
    split_dir = Path("/tmp/demo_audio_split")
    split_dir.mkdir(parents=True, exist_ok=True)
    _demo_split_dir = split_dir

    result: list[Path] = []
    for i in range(num_slides):
        start = i * segment_duration
        out_path = split_dir / f"slide_{i+1:03d}.mp3"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(combined_mp3),
            "-ss", str(start),
            "-t", str(segment_duration),
            "-c", "copy",
            str(out_path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and out_path.exists():
            result.append(out_path)
            logger.info("Demo: slide_{:03d}.mp3 (start={:.1f}s, dur={:.1f}s)", i+1, start, segment_duration)
        else:
            logger.error("Demo: failed slide_{:03d}.mp3: {}", i+1, r.stderr[:200])

    return result


@router.post("/screencast/demo/render")
async def demo_render(
    body: DemoRenderRequest,
    current_user: dict = Depends(get_current_user),
):
    """Queue a demo render job (Mode A: MP3 files exist) or serve pre-existing MP4 (Mode B).

    Mode A: per-slide MP3 files exist → full FFmpeg pipeline runs in Celery worker
    Mode B: no MP3 files → serve pre-existing MP4 immediately (no queue)
    """
    if db.get_setting("demo_data", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Demo-Modus ist nicht aktiviert")

    user_id = current_user.get("user_id", 0)
    if db.has_active_job_for_tool(user_id, ["screencast_render", "screencast_auto", "screencast_demo_render"]):
        raise HTTPException(status_code=409, detail="Du hast bereits einen laufenden Screencast-Render-Job.")

    pptx_path = _find_demo_pptx()
    if pptx_path:
        slide_texts = _extract_text_per_slide(pptx_path.read_bytes())
    else:
        slide_texts = _load_demo_scripts()
    num_slides_hint = len(slide_texts) or 6
    demo_audio = _load_demo_audio_files(num_slides_hint)

    # ── Mode A: MP3 files exist → queue Celery task ───────────────────────
    if demo_audio:
        job_uuid = uuid.uuid4().hex
        user_id = current_user.get("user_id", 0)
        db.create_job(job_uuid, user_id, "screencast_demo_render", "demo_screencast.pptx")

        from src.tasks.screencast_tasks import run_screencast_demo_render
        task = run_screencast_demo_render.apply_async(args=[job_uuid, body.file_id, body.dpi])
        db.set_job_celery_task_id(job_uuid, task.id)

        logger.info("Demo render job queued: job_uuid={}", job_uuid)
        return {"job_uuid": job_uuid}

    # ── Mode B: No MP3 files → serve pre-existing MP4 as-is ─────────────
    subtitle_data = _load_demo_subtitles()
    video_path = DEMO_DIR / "video.mp4"
    if not video_path.exists():
        for search_dir in [DEMO_DIR, DEMO_DIR / "slides"]:
            mp4_files = sorted(search_dir.glob("*.mp4"))
            if mp4_files:
                video_path = mp4_files[0]
                logger.info("Demo/render: found pre-built MP4 at {}", video_path.name)
                break

    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Keine Demo-MP3s und kein Demo-Video gefunden. "
                   "Lege slide_001.mp3 ... in backend/demo/slides/ ab.",
        )

    video_bytes = video_path.read_bytes()
    logger.info("Demo/render PASSTHROUGH: returning pre-built MP4 ({} bytes)", len(video_bytes))
    subtitle_json = json.dumps(subtitle_data)
    subtitle_b64 = base64.b64encode(subtitle_json.encode("utf-8")).decode("ascii")
    return StreamingResponse(
        iter([video_bytes]),
        media_type="video/mp4",
        headers={
            "Content-Length": str(len(video_bytes)),
            "X-Subtitles": subtitle_b64,
        },
    )
