"""Screencast route: translate DE PPTX → EN, extract text per slide, TTS, slide images, FFmpeg → MP4."""

import asyncio
import base64
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

# ── Per-job subprocess tracking for instant ffmpeg cancellation ──────────────
_job_procs: dict[str, list[subprocess.Popen]] = {}
_job_procs_lock = threading.Lock()


def _register_proc(job_uuid: str, proc: subprocess.Popen) -> None:
    with _job_procs_lock:
        _job_procs.setdefault(job_uuid, []).append(proc)


def _unregister_proc(job_uuid: str, proc: subprocess.Popen) -> None:
    with _job_procs_lock:
        procs = _job_procs.get(job_uuid, [])
        try:
            procs.remove(proc)
        except ValueError:
            pass


def kill_job_procs(job_uuid: str) -> None:
    """Kill all active ffmpeg subprocesses for a job (process group kill)."""
    with _job_procs_lock:
        procs = _job_procs.pop(job_uuid, [])
    for proc in procs:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _run_proc(cmd: list[str], timeout: int, job_uuid: str | None = None) -> subprocess.CompletedProcess:
    """Run a command in a new session (killable process group). Registers with job tracking."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    if job_uuid:
        _register_proc(job_uuid, proc)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            proc.kill()
        stdout, stderr = proc.communicate()
    finally:
        if job_uuid:
            _unregister_proc(job_uuid, proc)
    return subprocess.CompletedProcess(
        cmd, proc.returncode,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pydantic import BaseModel

from src.dependencies import get_deepl_client, get_elevenlabs_client, get_kisski_client, get_current_user, is_admin_user
from src.quotas import enforce_quota
from src.services.elevenlabs_client import ElevenLabsClient
from src.services.kisski_client import KisskiClient
from src.services.glossary import GlossaryService
from src.services.translation import TranslationService
from src.routes.translate import translate_pptx_content
from src.limits import MAX_QUEUED_SCREENCAST_JOBS, RENDER_MAX_WORKERS
from src.utils.file_validation import (
    MAX_OUTPUT_VIDEO_BYTES,
    MAX_SCREENCAST_SLIDES,
    MAX_UPLOAD_BYTES,
    SCREENCAST_EXTENSIONS,
    SCREENCAST_MAX_CHARS,
)
from src import database as db
from src.storage import save_queue_file, save_audio_cache, get_audio_slide, get_audio_slide_count, get_all_audio_slides, load_result_json, save_result_json, get_job_file, save_job_file, job_file_exists, delete_job_folder, clear_tts_audio_cache

router = APIRouter(tags=["screencast"])

# ── Temporary file storage (shared volume — accessible by celery-worker) ─────
PPTX_TMP_DIR = Path("/app/storage/screencast_tmp")
IMAGE_TMP_DIR = Path("/app/storage/screencast_tmp/images")

_cleanup_task: asyncio.Task | None = None

# Per-UUID lock: prevents concurrent script generation for the same job
_script_gen_locks: dict[str, asyncio.Lock] = {}


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
    """Save PPTX to temp storage (S3 or local) and return the file_id."""
    from src.storage import save_pptx_tmp as _storage_save_pptx
    file_id = uuid.uuid4().hex
    _storage_save_pptx(file_id, pptx_bytes)
    return file_id


# ── Pydantic models for step-by-step endpoints ──────────────────────────────

class ExtractTextsRequest(BaseModel):
    pptx_b64: str


class GenerateScriptsRequest(BaseModel):
    slide_texts: list[str]
    glossary_json: str = ""
    translate_job_uuid: str | None = None
    add_greeting: bool = True
    add_closing: bool = True
    min_chars: int = 1500
    max_chars: int = 2000
    source_lang: str = "DE"
    target_lang: str = "EN-US"


class ChatMessage(BaseModel):
    role: str
    content: str

class RegenerateSlideScriptRequest(BaseModel):
    slide_text: str = ""
    current_script: str | None = None
    user_prompt: str | None = None
    messages: list[ChatMessage] = []
    selected_text: str | None = None
    target_lang: str = "EN-US"


class PrepareRequest(BaseModel):
    translated_pptx_b64: str


class RenderRequest(BaseModel):
    scripts: list[str]
    translate_job_uuid: str          # the existing translate job to update
    slide_images_b64: list[str] = []
    voice_id: str = ""
    voice_label: str = ""
    speed: float = 1.0
    slide_pause: float = 0.5
    dpi: int = 100
    provider: str = "elevenlabs"


class PrerenderRequest(BaseModel):
    translate_job_uuid: str


async def _prerender_images_task(translate_job_uuid: str) -> None:
    """Background task: render slide images at 100 DPI and cache them in IMAGE_TMP_DIR."""
    from src.storage import get_job_file as _get_job_file

    out_dir = IMAGE_TMP_DIR / translate_job_uuid
    out_dir.mkdir(parents=True, exist_ok=True)

    # Read PPTX from job folder (corrected if available, else translated)
    pptx_data: bytes | None = None
    for filename in ("corrected.pptx", "translated.pptx"):
        try:
            pptx_data = _get_job_file(translate_job_uuid, filename)
            break
        except Exception:
            pass

    if pptx_data is None:
        logger.warning("Pre-render: PPTX not found in job folder for job={}", translate_job_uuid)
        return

    import tempfile as _tf
    tmp_f = _tf.NamedTemporaryFile(suffix=".pptx", delete=False)
    tmp_f.write(pptx_data)
    tmp_f.close()
    pptx_src = Path(tmp_f.name)

    try:
        await asyncio.to_thread(_pptx_to_images, pptx_src, out_dir, 100)
        logger.info("Pre-rendering complete for job={}", translate_job_uuid)
    except Exception as e:
        logger.warning("Pre-rendering failed for job={}: {}", translate_job_uuid, e)
    finally:
        pptx_src.unlink(missing_ok=True)


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


_A_T = '{http://schemas.openxmlformats.org/drawingml/2006/main}t'


def _collect_shape_text(shape, texts: list[str]) -> None:
    if shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            text = paragraph.text.strip()
            if text:
                texts.append(text)
    elif shape.has_table:
        for row in shape.table.rows:
            for cell in row.cells:
                for paragraph in cell.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        texts.append(text)
    elif shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for subshape in shape.shapes:
            _collect_shape_text(subshape, texts)
    else:
        # Fallback for SmartArt, graphic frames, and other non-standard shapes:
        # scan raw XML for any <a:t> text runs not already captured above.
        try:
            for t_elem in shape.element.iter(_A_T):
                text = (t_elem.text or "").strip()
                if text:
                    texts.append(text)
        except Exception:
            pass


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

    # Get page count via pdfinfo
    pdfinfo_result = subprocess.run(
        ["pdfinfo", str(pdf_path)], capture_output=True, text=True, timeout=30
    )
    page_count = 1
    for line in pdfinfo_result.stdout.splitlines():
        if line.startswith("Pages:"):
            page_count = int(line.split(":")[1].strip())
            break
    logger.info("PDF has {} pages, rendering in parallel", page_count)

    # Convert PDF pages to PNG in parallel — one pdftoppm process per page.
    slide_prefix = str(output_dir / "slide")

    def _render_page(page: int) -> None:
        cmd = [
            "pdftoppm", "-png", "-r", str(dpi),
            "-f", str(page), "-l", str(page),
            str(pdf_path), slide_prefix,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Seite {page} fehlgeschlagen: {result.stderr[:200]}")

    with ThreadPoolExecutor(max_workers=RENDER_MAX_WORKERS) as executor:
        futures = {executor.submit(_render_page, p): p for p in range(1, page_count + 1)}
        for future in as_completed(futures):
            future.result()  # re-raises on error

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


def _create_slide_video(image_path: Path, audio_path: Path | None, output_path: Path, pause: float = 0.0, crf: int = 23, job_uuid: str | None = None) -> None:
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
            "-loop", "1", "-framerate", "1", "-i", str(image_path),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "3",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
            "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "44100",
            "-shortest",
            str(output_path),
        ]
        result = _run_proc(cmd, timeout=300, job_uuid=job_uuid)
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
            "anullsrc=r=44100:cl=stereo",
            "-t", str(pause),
            "-ac", "2", "-ar", "44100",
            "-c:a", "libmp3lame", str(silence_path),
        ]
        _run_proc(cmd_silence, timeout=30, job_uuid=job_uuid)

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
        _run_proc(cmd_concat, timeout=30, job_uuid=job_uuid)
        final_audio = audio_with_pause_path
        total_duration = duration + pause
    else:
        final_audio = audio_path
        total_duration = duration

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "1", "-i", str(image_path),
        "-i", str(final_audio),
        "-t", str(total_duration),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
        "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "44100",
        "-shortest",
        str(output_path),
    ]
    result = _run_proc(cmd, timeout=300, job_uuid=job_uuid)
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



async def _generate_all_scripts(
    slide_texts: list[str],
    kisski_client: KisskiClient,
    glossary: dict | None = None,
    add_greeting: bool = True,
    add_closing: bool = True,
    min_chars: int = 1500,
    max_chars: int = 2000,
    source_lang: str = "DE",
    target_lang: str = "EN-US",
) -> list[str]:
    try:
        scripts = await asyncio.to_thread(
            kisski_client.generate_scripts_batch, slide_texts, glossary, add_greeting, add_closing,
            min_chars=min_chars, max_chars=max_chars, source_lang=source_lang, target_lang=target_lang,
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
    job_uuid: str | None = None,
) -> list[tuple[Path, dict | None]]:
    """Generate TTS audio for all slides in parallel via ElevenLabs.

    Returns a list of (audio_path, alignment_or_None) tuples.
    on_slide_done(current, total) is called after each slide completes.
    Each slide's audio is saved to persistent storage immediately after synthesis
    so a crash can be recovered without re-paying for completed slides.
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
            # Recovery: check if this slide was already synthesized in a previous (crashed) run
            if job_uuid:
                try:
                    audio_data = get_job_file(job_uuid, f"tts_audio/slide_{i:03d}.mp3")
                    audio_paths[i].write_bytes(audio_data)
                    try:
                        align_data = get_job_file(job_uuid, f"tts_audio/slide_{i:03d}_align.json")
                        alignments[i] = json.loads(align_data)
                    except Exception:
                        pass
                    logger.info("Slide {}/{}: loaded from storage (recovery)", i + 1, total)
                    async with lock:
                        counter += 1
                        if on_slide_done:
                            on_slide_done(counter, total)
                    return
                except Exception:
                    pass  # Not saved yet — synthesize normally

            async with sem:
                try:
                    result = await asyncio.to_thread(
                        tts_client.synthesize_with_timestamps,
                        script_text, "EN", voice_id=voice_id, speed=speed,
                    )
                    audio_bytes = result["audio_bytes"]
                    alignment = result["alignment"]
                    audio_paths[i].write_bytes(audio_bytes)
                    alignments[i] = alignment

                    # Save immediately to persistent storage for crash recovery
                    if job_uuid:
                        save_job_file(job_uuid, f"tts_audio/slide_{i:03d}.mp3", audio_bytes)
                        if alignment:
                            save_job_file(job_uuid, f"tts_audio/slide_{i:03d}_align.json",
                                          json.dumps(alignment).encode())

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
    voice_label: str = Form(""),
    speed: float = Form(1.0),
    dpi: int = Form(100),
    glossary_json: str = Form(""),
    provider: str = Form("elevenlabs"),
    source_lang: str = Form("DE"),
    target_lang: str = Form("EN-US"),
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
    if db.count_all_jobs_for_tool(user_id, _SCREENCAST_TOOLS) >= MAX_QUEUED_SCREENCAST_JOBS:
        raise HTTPException(status_code=409, detail=f"Du hast bereits {MAX_QUEUED_SCREENCAST_JOBS} Screencast-Jobs in der Warteschlange.")

    enforce_quota(user_id, "screencast", is_admin_user(current_user))
    job_uuid = uuid.uuid4().hex
    filename = file.filename or "screencast.pptx"
    db.create_job(job_uuid, user_id, "screencast_auto", filename)
    input_path = save_queue_file(job_uuid, ".pptx", pptx_bytes)
    db.set_job_input_path(job_uuid, input_path)

    # Always save params and queue; dispatch_next atomically dispatches if no active job
    save_job_file(job_uuid, "queue_params.json", json.dumps({
        "dispatch_as": "auto",
        "input_path": input_path,
        "filename": filename,
        "voice_id": voice_id,
        "speed": speed,
        "dpi": dpi,
        "glossary_json": glossary_json,
        "provider": provider,
        "voice_label": voice_label,
        "source_lang": source_lang,
        "target_lang": target_lang,
    }).encode())
    db.update_job_status(job_uuid, "queued")
    from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
    dispatch_next_screencast_job_for_user(user_id)
    logger.info("Screencast auto job submitted: job_uuid={}, file={}", job_uuid, filename)

    return {"job_uuid": job_uuid}


# ── Step-by-step endpoints ───────────────────────────────────────────────────

@router.post("/screencast/translate")
async def screencast_translate(
    request: Request,
    file: UploadFile = File(...),
    glossary_json: str = Form(""),
    fast_mode: bool = Form(False),
    source_lang: str = Form("DE"),
    target_lang: str = Form("EN-US"),
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
    if db.count_all_jobs_for_tool(user_id, _SCREENCAST_TOOLS) >= MAX_QUEUED_SCREENCAST_JOBS:
        raise HTTPException(status_code=409, detail=f"Du hast bereits {MAX_QUEUED_SCREENCAST_JOBS} Screencast-Jobs in der Warteschlange.")

    enforce_quota(user_id, "screencast", is_admin_user(current_user))
    job_uuid = uuid.uuid4().hex
    filename = file.filename or "screencast.pptx"
    db.create_job(job_uuid, user_id, "screencast_translate", filename)
    input_path = save_queue_file(job_uuid, ".pptx", pptx_bytes)
    db.set_job_input_path(job_uuid, input_path)

    # Always save params and queue; dispatch_next atomically dispatches if no active job
    save_job_file(job_uuid, "queue_params.json", json.dumps({
        "dispatch_as": "translate",
        "input_path": input_path,
        "filename": filename,
        "glossary_json": glossary_json,
        "fast_mode": fast_mode,
        "source_lang": source_lang,
        "target_lang": target_lang,
    }).encode())
    db.update_job_status(job_uuid, "queued")
    from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
    dispatch_next_screencast_job_for_user(user_id)
    logger.info("Screencast translate job submitted: job_uuid={}, file={}, fast_mode={}", job_uuid, filename, fast_mode)

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


@router.get("/screencast/{job_uuid}/images")
async def get_job_slide_images(job_uuid: str, current_user: dict = Depends(get_current_user)):
    """Return slide images (base64) for a translate/demo job — rendered from saved PPTX."""
    if not re.match(r"^[a-f0-9]{32}$", job_uuid):
        raise HTTPException(status_code=400, detail="Ungültige Job-UUID")
    job = db.get_job(job_uuid)
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail="Job nicht gefunden")

    # Try to load from result JSON first (fast path for jobs that stored images)
    if job.get("result_path"):
        try:
            result_data = load_result_json(job["result_path"])
            imgs = result_data.get("slide_images", [])
            if imgs:
                return {"slide_images": imgs}
        except Exception:
            pass

    # Fallback: re-render from saved translated.pptx
    pptx_bytes: bytes | None = None
    for filename in ("corrected.pptx", "translated.pptx"):
        try:
            pptx_bytes = get_job_file(job_uuid, filename)
            break
        except Exception:
            pass
    if not pptx_bytes:
        raise HTTPException(status_code=404, detail="PPTX nicht mehr verfügbar")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pptx_path = tmp / "presentation.pptx"
        pptx_path.write_bytes(pptx_bytes)
        img_dir = tmp / "images"
        img_dir.mkdir()
        try:
            slide_image_paths = await _convert_slides_to_images_async(pptx_path, img_dir)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in slide_image_paths]

    return {"slide_images": slide_images_b64}


@router.get("/screencast/pptx/{translate_job_uuid}")
async def download_pptx_file(translate_job_uuid: str, current_user: dict = Depends(get_current_user)):
    """Download translated/corrected PPTX from job folder."""
    from src.storage import get_job_file as _get_job_file
    if not re.match(r"^[a-f0-9]{32}$", translate_job_uuid):
        raise HTTPException(status_code=400, detail="Ungültige job UUID")
    job = db.get_job(translate_job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Job")
    data: bytes | None = None
    for filename in ("corrected.pptx", "translated.pptx"):
        try:
            data = _get_job_file(translate_job_uuid, filename)
            break
        except Exception:
            pass
    if data is None:
        raise HTTPException(status_code=404, detail="PPTX nicht gefunden")
    logger.info("Serving PPTX for job={} ({} bytes)", translate_job_uuid, len(data))
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": 'attachment; filename="translated.pptx"',
        },
    )


class SaveScriptsRequest(BaseModel):
    scripts: list[str]
    accepted: bool = False  # True = "Alle Skripte übernehmen" clicked
    user_prompt: str | None = None


@router.patch("/screencast/scripts/{translate_job_uuid}")
async def save_scripts(
    translate_job_uuid: str,
    body: SaveScriptsRequest,
    current_user: dict = Depends(get_current_user),
):
    """Autosave or accept scripts for a screencast job (awaiting_user)."""
    if not re.match(r"^[a-f0-9]{32}$", translate_job_uuid):
        raise HTTPException(status_code=400, detail="Ungültige Job-UUID")
    job = db.get_job(translate_job_uuid)
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job["status"] not in ("awaiting_user", "success"):
        raise HTTPException(status_code=409, detail="Job ist nicht im Eingabe-Status")
    filename = "accepted_scripts.json" if body.accepted else "user_scripts.json"
    save_job_file(translate_job_uuid, filename, json.dumps(body.scripts, ensure_ascii=False).encode())
    if body.user_prompt is not None:
        save_job_file(translate_job_uuid, "prompt.txt", body.user_prompt.encode())
    return {"ok": True}


@router.get("/screencast/resume/{translate_job_uuid}")
async def get_resume_data(translate_job_uuid: str, current_user: dict = Depends(get_current_user)):
    """Reconstruct workflow state from job folder for resuming an awaiting_user screencast job."""
    if not re.match(r"^[a-f0-9]{32}$", translate_job_uuid):
        raise HTTPException(status_code=400, detail="Ungültige Job-UUID")
    job = db.get_job(translate_job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Job")
    if job["status"] != "awaiting_user":
        raise HTTPException(status_code=409, detail="Job ist nicht im Eingabe-Status")

    tool = job["tool"]
    slide_texts: list[str] = []
    scripts: list[str] = []
    slide_images: list[str] = []
    user_prompt = ""
    step = "script-review"

    try:
        user_prompt = get_job_file(translate_job_uuid, "prompt.txt").decode()
    except Exception:
        pass

    # Step detection:
    #   accepted_scripts.json  → tts-settings (step 6)
    #   user_scripts.json      → script-review (step 5, user edits)
    #   suggested_scripts.json → script-review (step 5, KI suggestion)
    #   nothing                → user-prompt or translation-review
    SCRIPT_FILES = (
        ("accepted_scripts.json", "tts-settings"),
        ("user_scripts.json", "script-review"),
        ("suggested_scripts.json", "script-review"),
    )

    if tool == "screencast_translate":
        try:
            slide_texts = json.loads(get_job_file(translate_job_uuid, "scripts.txt"))
        except Exception:
            raise HTTPException(status_code=404, detail="Job-Daten nicht mehr verfügbar — bitte neuen Screencast starten")

        # Load slide images from result JSON (stored there by the translate task)
        try:
            if job.get("result_path"):
                result_data = load_result_json(job["result_path"])
                slide_images = result_data.get("slide_images", [])
        except Exception:
            pass

        for filename, resolved_step in SCRIPT_FILES:
            try:
                scripts = json.loads(get_job_file(translate_job_uuid, filename))
                step = resolved_step
                break
            except Exception:
                pass

        if not scripts:
            step = "user-prompt" if user_prompt else "translation-review"

    elif tool == "screencast_demo_render":
        try:
            slide_texts = json.loads(get_job_file(translate_job_uuid, "scripts.txt"))
        except Exception:
            pass

        # Load slide images from result JSON (stored there by the task)
        try:
            if job.get("result_path"):
                result_data = load_result_json(job["result_path"])
                slide_images = result_data.get("slide_images", [])
        except Exception:
            pass

        # Step detection
        step = "translation-review"
        for filename, resolved_step in SCRIPT_FILES:
            try:
                scripts = json.loads(get_job_file(translate_job_uuid, filename))
                step = resolved_step
                break
            except Exception:
                pass
        if not scripts:
            step = "user-prompt" if user_prompt else "translation-review"

    return {
        "tool": tool,
        "step": step,
        "slide_texts": slide_texts,
        "scripts": scripts,
        "slide_images": slide_images,
        "original_filename": job["original_filename"] or "",
        "user_prompt": user_prompt,
    }


@router.get("/screencast/folder-exists/{translate_job_uuid}")
async def check_folder_exists(translate_job_uuid: str, current_user: dict = Depends(get_current_user)):
    """Check if the job folder (scripts.txt) still exists in storage. Lightweight pre-flight check."""
    if not re.match(r"^[a-f0-9]{32}$", translate_job_uuid):
        raise HTTPException(status_code=400, detail="Ungültige Job-UUID")
    job = db.get_job(translate_job_uuid)
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    try:
        get_job_file(translate_job_uuid, "scripts.txt")
        return {"exists": True}
    except Exception:
        return {"exists": False}


@router.post("/screencast/upload-corrected")
async def screencast_upload_corrected(
    request: Request,
    file: UploadFile = File(...),
    translate_job_uuid: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """Upload a corrected PPTX, save to temp storage + job folder, extract texts and slide images."""
    _validate_upload(file.filename)
    _maybe_start_cleanup_task()

    pptx_bytes = await file.read()
    if not pptx_bytes:
        raise HTTPException(status_code=400, detail="Datei ist leer")

    logger.info("Screencast/upload-corrected: '{}' ({} bytes)", file.filename, len(pptx_bytes))

    # Validate job ownership if translate_job_uuid provided
    if translate_job_uuid:
        job = db.get_job(translate_job_uuid)
        if not job:
            raise HTTPException(status_code=404, detail="Job nicht gefunden")
        if job["user_id"] != current_user.get("user_id", 0):
            raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Job")

    slide_texts = _extract_text_per_slide(pptx_bytes)
    if not slide_texts:
        raise HTTPException(status_code=400, detail="Keine Slides in der Präsentation gefunden")

    if len(slide_texts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(slide_texts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    from src.storage import save_job_file as _save_job_file

    if translate_job_uuid:
        # Existing job: save as corrected.pptx (user re-uploaded after translation)
        _save_job_file(translate_job_uuid, "corrected.pptx", pptx_bytes)
        logger.info("Saved corrected.pptx to job folder {}", translate_job_uuid)
    else:
        # No job yet (EN path): create a new translate job and save PPTX as translated.pptx
        user_id = current_user.get("user_id", 0)
        _SCREENCAST_TOOLS = ["screencast_translate", "screencast_render", "screencast_auto", "screencast_demo_render"]
        if db.count_all_jobs_for_tool(user_id, _SCREENCAST_TOOLS) >= MAX_QUEUED_SCREENCAST_JOBS:
            raise HTTPException(status_code=409, detail=f"Du hast bereits {MAX_QUEUED_SCREENCAST_JOBS} Screencast-Jobs in der Warteschlange.")
        enforce_quota(user_id, "screencast", is_admin_user(current_user))
        translate_job_uuid = uuid.uuid4().hex
        db.create_job(translate_job_uuid, user_id, "screencast_translate", file.filename or "screencast.pptx")
        _save_job_file(translate_job_uuid, "translated.pptx", pptx_bytes)
        _save_job_file(translate_job_uuid, "scripts.txt", json.dumps(slide_texts, ensure_ascii=False, indent=2).encode("utf-8"))
        db.update_job_status(translate_job_uuid, "awaiting_user")
        db.update_job_expiry(translate_job_uuid, 168)
        logger.info("Created translate job {} for EN upload ({})", translate_job_uuid, file.filename)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pptx_path = tmp / "upload.pptx"
        pptx_path.write_bytes(pptx_bytes)
        img_dir = tmp / "images"
        img_dir.mkdir()
        try:
            slide_image_paths = await _convert_slides_to_images_async(pptx_path, img_dir)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in slide_image_paths]

    return {
        "translate_job_uuid": translate_job_uuid,
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
        "Screencast/generate-scripts: {} slides, greeting={}, closing={}",
        len(body.slide_texts), body.add_greeting, body.add_closing,
    )

    kisski_client = get_kisski_client()
    glossary_dict: dict | None = None
    if body.glossary_json:
        try:
            glossary_dict = json.loads(body.glossary_json)
        except (json.JSONDecodeError, TypeError):
            pass

    uuid_key = body.translate_job_uuid if (body.translate_job_uuid and re.match(r"^[a-f0-9]{32}$", body.translate_job_uuid)) else None

    # Verify job folder still exists before burning LLM tokens
    if uuid_key:
        try:
            get_job_file(uuid_key, "scripts.txt")
        except Exception:
            raise HTTPException(status_code=410, detail="Job-Daten nicht mehr verfügbar — bitte neuen Screencast starten")

    async def _do_generate() -> list[str]:
        return await _generate_all_scripts(
            body.slide_texts, kisski_client,
            glossary=glossary_dict,
            add_greeting=body.add_greeting, add_closing=body.add_closing,
            min_chars=body.min_chars, max_chars=body.max_chars,
            source_lang=body.source_lang, target_lang=body.target_lang,
        )

    if not uuid_key:
        return {"scripts": await _do_generate()}

    if uuid_key not in _script_gen_locks:
        _script_gen_locks[uuid_key] = asyncio.Lock()
    lock = _script_gen_locks[uuid_key]

    if lock.locked():
        # Another request is already generating for this job — wait, then return its result
        logger.info("generate-scripts: waiting for concurrent generation of {}", uuid_key)
        async with lock:
            # The other request just finished; read what it saved
            try:
                data = get_job_file(uuid_key, "suggested_scripts.json")
                return {"scripts": json.loads(data)}
            except Exception:
                pass
        # File missing after wait (other request failed) — fall through to regenerate.
        # The lock is now FREE (we released it above), so the acquire below is safe.

    async with lock:
        db.set_generating_scripts_flag(uuid_key, True)
        try:
            scripts = await _do_generate()
        finally:
            db.set_generating_scripts_flag(uuid_key, False)
        try:
            save_job_file(uuid_key, "suggested_scripts.json", json.dumps(scripts, ensure_ascii=False).encode())
        except Exception:
            pass

    return {"scripts": scripts}


@router.post("/screencast/regenerate-slide-script")
async def screencast_regenerate_slide_script(body: RegenerateSlideScriptRequest):
    """Regenerate the narration script for a single slide via KISSKI LLM.

    Called from Step 5 when the user clicks the AI icon next to a slide.
    Uses a single LLM call (no batching) so user_prompt is fully reliable.
    """
    # Need at least one source of input
    user_prompt = body.user_prompt or (body.messages[-1].content if body.messages else "")
    has_content = (
        body.slide_text.strip()
        or (body.current_script or "").strip()
        or user_prompt.strip()
    )
    if not has_content:
        return {"script": ""}

    kisski_client = get_kisski_client()

    try:
        script = await asyncio.to_thread(
            kisski_client.refine_script,
            user_prompt,
            body.current_script or "",
            body.slide_text,
            body.target_lang,
            body.selected_text or None,
            [{"role": m.role, "content": m.content} for m in body.messages],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Skript-Generierung fehlgeschlagen: {e}")

    return {"script": script}


@router.post("/screencast/prerender-images")
async def prerender_images(body: PrerenderRequest, background_tasks: BackgroundTasks):
    """Start background pre-rendering of slide images at 300 DPI.

    Call this after the user confirms scripts so images are ready when /render is called.
    Fire-and-forget: always returns immediately.
    """
    if not re.match(r"^[a-f0-9]{32}$", body.translate_job_uuid):
        raise HTTPException(status_code=400, detail="Ungültige job UUID")
    background_tasks.add_task(_prerender_images_task, body.translate_job_uuid)
    logger.info("Pre-render started for job={}", body.translate_job_uuid)
    return {"status": "started"}


@router.post("/screencast/render")
async def screencast_render(
    body: RenderRequest,
    current_user: dict = Depends(get_current_user),
):
    """Queue render phase on the existing translate job (single-folder workflow)."""
    if not body.scripts:
        raise HTTPException(status_code=400, detail="Keine Skripte übergeben")

    if len(body.scripts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(body.scripts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    total_chars = sum(len(s) for s in body.scripts)
    if total_chars > SCREENCAST_MAX_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"Das Skript ist zu lang ({total_chars:,} Zeichen). Maximum: {SCREENCAST_MAX_CHARS:,} Zeichen.",
        )

    user_id = current_user.get("user_id", 0)

    # Validate translate job ownership + status
    translate_job = db.get_job(body.translate_job_uuid)
    if not translate_job:
        raise HTTPException(status_code=404, detail="Translate-Job nicht gefunden")
    if translate_job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Job")
    if translate_job["status"] not in ("awaiting_user", "failed", "success"):
        raise HTTPException(status_code=409, detail="Job ist nicht bereit zum Rendern")
    if not job_file_exists(body.translate_job_uuid, "translated.pptx"):
        delete_job_folder(body.translate_job_uuid)
        db.delete_job(body.translate_job_uuid)
        raise HTTPException(status_code=404, detail="Job-Dateien nicht mehr vorhanden. Bitte neue Übersetzung starten.")

    # If re-rendering a previously completed job, clear stale TTS audio so the
    # crash-recovery mechanism doesn't reuse old audio for the new scripts.
    original_status = translate_job["status"]
    if original_status == "success":
        clear_tts_audio_cache(body.translate_job_uuid)
        logger.info("Re-render: cleared TTS audio cache for job={}", body.translate_job_uuid)

    # Save scripts and render params for queue dispatch (used by dispatch_next)
    save_job_file(body.translate_job_uuid, "render_scripts.json", json.dumps(body.scripts, ensure_ascii=False).encode())
    save_job_file(body.translate_job_uuid, "queue_params.json", json.dumps({
        "dispatch_as": "render",
        "voice_id": body.voice_id,
        "speed": body.speed,
        "slide_pause": body.slide_pause,
        "dpi": body.dpi,
        "provider": body.provider,
        "voice_label": body.voice_label,
        "is_admin": is_admin_user(current_user),
    }).encode())

    # Atomically transition to queued (prevents duplicate submissions from multiple tabs)
    transitioned = db.transition_job_to_queued(
        body.translate_job_uuid,
        user_id,
        from_statuses=("awaiting_user", "failed", "success"),
    )
    if not transitioned:
        raise HTTPException(
            status_code=409,
            detail="Dieser Job wird bereits verarbeitet.",
        )

    from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
    dispatch_next_screencast_job_for_user(user_id)

    logger.info("Screencast render queued: translate_job={}", body.translate_job_uuid)
    return {"job_uuid": body.translate_job_uuid}


# ── Audio download endpoints ──────────────────────────────────────────────────

@router.get("/screencast/audio/{audio_id}/zip")
async def download_all_slide_audio_zip(audio_id: str):
    """Download all per-slide MP3s as a single ZIP archive."""
    slides = get_all_audio_slides(audio_id)
    if not slides:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden (abgelaufen oder ungültige ID)")

    buf = BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED) as zf:
        for filename, data in slides:
            zf.writestr(filename, data)
    buf.seek(0)
    zip_bytes = buf.read()

    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={
            "Content-Length": str(len(zip_bytes)),
            "Content-Disposition": f'attachment; filename="folien_audio.zip"',
        },
    )


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
