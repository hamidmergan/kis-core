"""Screencast route: translate DE PPTX → EN, extract text per slide, TTS, slide images, FFmpeg → MP4."""

import asyncio
import base64
import json
import re
import subprocess
import tempfile
import uuid
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pydantic import BaseModel

from src.dependencies import get_deepl_client, get_elevenlabs_client, get_kisski_client, get_settings
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

router = APIRouter(tags=["screencast"])

# ── Temporary audio cache (render ID → list of MP3 bytes) ────────────────────
_audio_cache: dict[str, list[bytes]] = {}


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
    translated_pptx_b64: str
    slide_images_b64: list[str]
    voice_id: str = ""
    speed: float = 0.9
    slide_pause: float = 0.5
    embed_subtitles: bool = True
    image_dpi: int = 150
    video_crf: int = 23


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


def _pptx_to_images(pptx_path: Path, output_dir: Path, dpi: int = 150) -> list[Path]:
    """Convert PPTX slides to PNG images using LibreOffice."""
    # First convert PPTX to PDF via LibreOffice
    cmd = [
        "libreoffice", "--headless", "--convert-to", "pdf",
        "--outdir", str(output_dir), str(pptx_path),
    ]
    logger.info("Converting PPTX to PDF: {}", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.error("LibreOffice conversion failed: {}", result.stderr[:300])
        raise RuntimeError(f"LibreOffice Konvertierung fehlgeschlagen: {result.stderr[:200]}")

    pdf_path = output_dir / f"{pptx_path.stem}.pdf"
    if not pdf_path.exists():
        raise RuntimeError("LibreOffice hat keine PDF-Datei erstellt")

    # Convert PDF pages to individual PNG images using pdftoppm (poppler-utils)
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
    return images


def _get_audio_duration(audio_path: Path) -> float:
    """Get the exact duration of an audio file in seconds using ffprobe."""
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


def _create_slide_video(image_path: Path, audio_path: Path, output_path: Path, pause: float = 0.0, crf: int = 23) -> None:
    """Combine a single slide image with its audio into a video clip."""
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
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error("Slide video creation failed: {}", result.stderr[:300])
        raise RuntimeError(f"Video-Erstellung fehlgeschlagen: {result.stderr[:200]}")


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
) -> list[tuple[Path, dict | None]]:
    """Generate TTS audio for all slides in parallel via ElevenLabs.

    Returns a list of (audio_path, alignment_or_None) tuples.
    """
    sem = asyncio.Semaphore(5)
    audio_paths: list[Path] = [tmp / f"slide_{i:03d}.mp3" for i in range(len(slide_scripts))]
    alignments: list[dict | None] = [None] * len(slide_scripts)

    async def _tts(i: int, script_text: str) -> None:
        audio_path = audio_paths[i]
        if not script_text.strip():
            # Empty slide: create 2 seconds of silence
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                "anullsrc=r=44100:cl=mono", "-t", "2",
                "-c:a", "libmp3lame", str(audio_path),
            ]
            await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=30
            )
            return
        async with sem:
            try:
                result = await asyncio.to_thread(
                    tts_client.synthesize_with_timestamps,
                    script_text, "EN", voice_id=voice_id, speed=speed,
                )
                audio_path.write_bytes(result["audio_bytes"])
                alignments[i] = result["alignment"]
                logger.info("TTS for slide {}/{} done", i + 1, len(slide_scripts))
            except Exception as e:
                logger.error("TTS failed for slide {}: {}", i + 1, e)
                raise HTTPException(
                    status_code=502,
                    detail=f"TTS-Fehler bei Folie {i + 1}: {e}",
                )

    await asyncio.gather(*[_tts(i, t) for i, t in enumerate(slide_scripts)])
    return list(zip(audio_paths, alignments))


# PARALLELIZED
async def _convert_slides_to_images_async(
    pptx_path: Path, img_dir: Path
) -> list[Path]:
    """Run LibreOffice image conversion in a thread."""
    return await asyncio.to_thread(_pptx_to_images, pptx_path, img_dir)


# ── Auto-mode endpoint (unchanged) ──────────────────────────────────────────

@router.post("/screencast")
async def screencast(
    request: Request,
    file: UploadFile = File(...),
    voice_id: str = Form(""),
    speed: float = Form(0.9),
    glossary_json: str = Form(""),
):
    """Create a screencast video from a German PPTX presentation.

    Translates DE→EN, generates TTS per slide, converts slides to images,
    and combines everything into a single MP4 video.
    """
    _validate_upload(file.filename)

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    pptx_bytes = await file.read()
    if not pptx_bytes:
        raise HTTPException(status_code=400, detail="Datei ist leer")

    stem = Path(file.filename).stem  # type: ignore[arg-type]
    logger.info("Screencast: processing '{}' ({} bytes)", file.filename, len(pptx_bytes))

    # ── Step 1: Translate PPTX DE → EN ────────────────────────────────────
    logger.info("Step 1: Translating PPTX DE → EN")
    translated_bytes = translate_pptx_content(pptx_bytes, file.filename, glossary_json)

    # ── Step 2: Extract text per slide ────────────────────────────────────
    logger.info("Step 2: Extracting text per slide")
    slide_texts = _extract_text_per_slide(translated_bytes)
    if not slide_texts:
        raise HTTPException(status_code=400, detail="Keine Slides in der Präsentation gefunden")
    logger.info("Found {} slides", len(slide_texts))

    # ── Validate slide count ──────────────────────────────────────────────
    if len(slide_texts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(slide_texts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Save translated PPTX for image conversion
        translated_pptx_path = tmp / "translated.pptx"
        translated_pptx_path.write_bytes(translated_bytes)
        img_dir = tmp / "images"
        img_dir.mkdir()

        # PARALLELIZED
        # ── Steps 3 + 5: Generate scripts & convert slides to images concurrently
        logger.info("Steps 3+5: Generating scripts and converting slides to images (parallel)")
        kisski_client = get_kisski_client()
        glossary_dict: dict | None = None
        if glossary_json:
            try:
                glossary_dict = json.loads(glossary_json)
            except (json.JSONDecodeError, TypeError):
                pass
        try:
            slide_scripts, slide_images = await asyncio.gather(
                _generate_all_scripts(slide_texts, kisski_client, glossary=glossary_dict),
                _convert_slides_to_images_async(translated_pptx_path, img_dir),
            )
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

        # PARALLELIZED
        # ── Step 4: TTS per slide ─────────────────────────────────────────
        logger.info("Step 4: Generating TTS audio per slide (parallel)")
        tts_client = get_elevenlabs_client()
        tts_results = await _generate_all_tts(slide_scripts, tts_client, tmp, speed, voice_id)
        audio_paths = [r[0] for r in tts_results]
        alignments = [r[1] for r in tts_results]

        # Ensure we have matching counts (use min of both)
        num_slides = min(len(slide_images), len(audio_paths))
        if num_slides == 0:
            raise HTTPException(status_code=500, detail="Keine Slides verarbeitet")

        # ── Step 6: Create video per slide ────────────────────────────────
        logger.info("Step 6: Creating video clips per slide")
        clip_paths: list[Path] = []
        for i in range(num_slides):
            clip_path = tmp / f"clip_{i:03d}.mp4"
            try:
                _create_slide_video(slide_images[i], audio_paths[i], clip_path, pause=0.5)
            except RuntimeError as e:
                raise HTTPException(status_code=500, detail=str(e))
            clip_paths.append(clip_path)
            logger.info("Clip {}/{} done", i + 1, num_slides)

        # ── Step 7: Concatenate all clips ─────────────────────────────────
        logger.info("Step 7: Concatenating clips")
        concat_path = tmp / "concat.mp4"
        try:
            _concatenate_videos(clip_paths, concat_path)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

        # ── Step 7b: Build & embed subtitles ──────────────────────────────
        per_slide_data = []
        for i in range(num_slides):
            dur = _get_audio_duration(audio_paths[i])
            per_slide_data.append({"alignment": alignments[i], "audio_duration": dur})
        subtitle_data = build_subtitles(per_slide_data, slide_pause=0.5)

        if subtitle_data["srt"]:
            srt_path = tmp / "subtitles.srt"
            srt_path.write_text(subtitle_data["srt"], encoding="utf-8")
            subtitled_path = tmp / "concat_sub.mp4"
            if _embed_subtitles(concat_path, srt_path, subtitled_path):
                concat_path = subtitled_path
            else:
                logger.warning("Auto-mode: subtitle embedding failed, video has no subtitles")
        else:
            logger.warning("Auto-mode: no SRT data generated (empty alignment?)")

        # ── Step 8: Apply faststart ───────────────────────────────────────
        logger.info("Step 8: Applying faststart")
        final_path = tmp / "final.mp4"
        output_bytes = _apply_faststart(concat_path, final_path)

    # ── Validate output video size ────────────────────────────────────────
    if len(output_bytes) > MAX_OUTPUT_VIDEO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Das generierte Video ist zu groß ({len(output_bytes) // (1024*1024)} MB). Maximum: 500 MB. Bitte verwenden Sie eine Präsentation mit weniger Folien.",
        )

    output_name = f"{stem}_screencast_EN.mp4"
    encoded_name = quote(output_name, safe="")
    logger.info("Screencast complete: '{}', size={} bytes", output_name, len(output_bytes))

    return StreamingResponse(
        iter([output_bytes]),
        media_type="video/mp4",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{encoded_name}"; '
                f"filename*=UTF-8''{encoded_name}"
            ),
            "Content-Length": str(len(output_bytes)),
            "Accept-Ranges": "bytes",
        },
    )


# ── Step-by-step endpoints ───────────────────────────────────────────────────

@router.post("/screencast/translate")
async def screencast_translate(
    request: Request,
    file: UploadFile = File(...),
    glossary_json: str = Form(""),
):
    """Translate PPTX DE→EN and extract slide texts."""
    _validate_upload(file.filename)

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    pptx_bytes = await file.read()
    if not pptx_bytes:
        raise HTTPException(status_code=400, detail="Datei ist leer")

    logger.info("Screencast/translate: processing '{}' ({} bytes)", file.filename, len(pptx_bytes))

    # ── Step 1: Translate PPTX DE → EN ────────────────────────────────────
    logger.info("Step 1: Translating PPTX DE → EN")
    translated_bytes = translate_pptx_content(pptx_bytes, file.filename, glossary_json)

    # ── Step 2: Extract text per slide ────────────────────────────────────
    logger.info("Step 2: Extracting text per slide")
    slide_texts = _extract_text_per_slide(translated_bytes)
    if not slide_texts:
        raise HTTPException(status_code=400, detail="Keine Slides in der Präsentation gefunden")
    logger.info("Found {} slides", len(slide_texts))

    # ── Validate slide count ──────────────────────────────────────────────
    if len(slide_texts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(slide_texts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        translated_pptx_path = tmp / "translated.pptx"
        translated_pptx_path.write_bytes(translated_bytes)
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

    translated_pptx_b64 = base64.b64encode(translated_bytes).decode()

    return {
        "slide_count": len(slide_texts),
        "slide_texts": slide_texts,
        "slide_images": slide_images_b64,
        "translated_pptx_b64": translated_pptx_b64,
    }


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


@router.post("/screencast/render")
async def screencast_render(body: RenderRequest):
    """Render final MP4 from edited scripts and translated PPTX."""
    if not body.scripts:
        raise HTTPException(status_code=400, detail="Keine Skripte übergeben")

    if len(body.scripts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(body.scripts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    logger.info("Screencast/render: {} slides, speed={}", len(body.scripts), body.speed)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Decode slide images — re-extract at higher DPI if requested
        if body.image_dpi != 150:
            logger.info("Re-extracting slide images at {} DPI", body.image_dpi)
            pptx_bytes = base64.b64decode(body.translated_pptx_b64)
            hi_pptx_path = tmp / "translated.pptx"
            hi_pptx_path.write_bytes(pptx_bytes)
            img_dir = tmp / "images"
            img_dir.mkdir()
            slide_images = await asyncio.to_thread(
                _pptx_to_images, hi_pptx_path, img_dir, body.image_dpi
            )
        else:
            slide_images: list[Path] = []
            for i, img_b64 in enumerate(body.slide_images_b64):
                img_path = tmp / f"slide_{i:03d}.png"
                img_path.write_bytes(base64.b64decode(img_b64))
                slide_images.append(img_path)

        # Generate TTS audio
        tts_client = get_elevenlabs_client()
        tts_results = await _generate_all_tts(body.scripts, tts_client, tmp, body.speed, body.voice_id)
        audio_paths = [r[0] for r in tts_results]
        alignments = [r[1] for r in tts_results]

        # Ensure we have matching counts (use min of both)
        num_slides = min(len(slide_images), len(audio_paths))
        if num_slides == 0:
            raise HTTPException(status_code=500, detail="Keine Slides verarbeitet")

        # ── Create video per slide ────────────────────────────────────────
        logger.info("Creating video clips per slide")
        clip_paths: list[Path] = []
        for i in range(num_slides):
            clip_path = tmp / f"clip_{i:03d}.mp4"
            try:
                _create_slide_video(slide_images[i], audio_paths[i], clip_path, pause=body.slide_pause, crf=body.video_crf)
            except RuntimeError as e:
                raise HTTPException(status_code=500, detail=str(e))
            clip_paths.append(clip_path)
            logger.info("Clip {}/{} done", i + 1, num_slides)

        # ── Concatenate all clips ─────────────────────────────────────────
        logger.info("Concatenating clips")
        concat_path = tmp / "concat.mp4"
        try:
            _concatenate_videos(clip_paths, concat_path)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

        # ── Build subtitles ───────────────────────────────────────────────
        per_slide_data = []
        for i in range(num_slides):
            dur = _get_audio_duration(audio_paths[i])
            per_slide_data.append({"alignment": alignments[i], "audio_duration": dur})
        subtitle_data = build_subtitles(per_slide_data, slide_pause=body.slide_pause)

        # ── Optionally embed subtitles into MP4 ──────────────────────────
        if body.embed_subtitles and subtitle_data["srt"]:
            srt_path = tmp / "subtitles.srt"
            srt_path.write_text(subtitle_data["srt"], encoding="utf-8")
            logger.info("SRT content length: {} chars", len(subtitle_data["srt"]))
            subtitled_path = tmp / "concat_sub.mp4"
            if _embed_subtitles(concat_path, srt_path, subtitled_path):
                concat_path = subtitled_path
            else:
                logger.warning("Render: subtitle embedding failed, video has no subtitles")
        elif body.embed_subtitles:
            logger.warning("Render: embed_subtitles=True but no SRT data (empty alignment?)")

        # ── Cache per-slide MP3 audio bytes ──────────────────────────────
        audio_id = uuid.uuid4().hex
        _audio_cache[audio_id] = [ap.read_bytes() for ap in audio_paths[:num_slides]]
        logger.info("Cached {} audio files under id={}", num_slides, audio_id)

        # ── Apply faststart ───────────────────────────────────────────────
        logger.info("Applying faststart")
        final_path = tmp / "final.mp4"
        output_bytes = _apply_faststart(concat_path, final_path)

    # ── Validate output video size ────────────────────────────────────────
    if len(output_bytes) > MAX_OUTPUT_VIDEO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Das generierte Video ist zu groß ({len(output_bytes) // (1024*1024)} MB). Maximum: 500 MB. Bitte verwenden Sie eine Präsentation mit weniger Folien.",
        )

    logger.info("Screencast/render complete, size={} bytes", len(output_bytes))
    logger.info("Screencast/render final streams: {}", _probe_streams(final_path if final_path.exists() else concat_path))

    subtitle_json = json.dumps(subtitle_data)
    subtitle_b64 = base64.b64encode(subtitle_json.encode("utf-8")).decode("ascii")

    return StreamingResponse(
        iter([output_bytes]),
        media_type="video/mp4",
        headers={
            "Content-Length": str(len(output_bytes)),
            "X-Subtitles": subtitle_b64,
            "X-Audio-Id": audio_id,
            "X-Audio-Count": str(num_slides),
        },
    )


# ── Audio download endpoint ──────────────────────────────────────────────────

@router.get("/screencast/audio/{audio_id}/{slide_index}")
async def download_slide_audio(audio_id: str, slide_index: int):
    """Download a single per-slide MP3 from the render audio cache."""
    files = _audio_cache.get(audio_id)
    if not files:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden (abgelaufen oder ungültige ID)")
    if slide_index < 0 or slide_index >= len(files):
        raise HTTPException(status_code=404, detail=f"Folie {slide_index + 1} nicht gefunden")

    audio_bytes = files[slide_index]
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
    srt_path = DEMO_DIR / "slides" / "transcript.srt"
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
        "srt": "transcript.srt",
        "vtt": "transcript.vtt",
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
    settings = get_settings()
    pptx_exists = _find_demo_pptx() is not None
    video_exists = (DEMO_DIR / "video.mp4").exists()
    if not video_exists:
        for search_dir in [DEMO_DIR, DEMO_DIR / "slides"]:
            if search_dir.exists() and list(search_dir.glob("*.mp4")):
                video_exists = True
                break
    return {
        "available": settings.demo_data and pptx_exists,
        "has_video": settings.demo_data and video_exists,
        "demo_data_enabled": settings.demo_data,
        "pptx_exists": pptx_exists,
        "video_exists": video_exists,
    }


@router.post("/screencast/demo/translate")
async def demo_translate():
    """Return demo translation data (slide images, texts, translated PPTX).

    Requires a PPTX file in demo/slides/. Reads user prompt from Anweisung.txt.
    """
    settings = get_settings()
    if not settings.demo_data:
        raise HTTPException(status_code=403, detail="Demo-Modus ist nicht aktiviert")

    pptx_path = _find_demo_pptx()
    if not pptx_path:
        raise HTTPException(status_code=404, detail="Keine PPTX in demo/slides/ gefunden")

    user_prompt = _load_demo_user_prompt()

    logger.info("Demo/translate: using PPTX '{}'", pptx_path.name)
    pptx_bytes = pptx_path.read_bytes()
    translated_pptx_b64 = base64.b64encode(pptx_bytes).decode()

    slide_texts = _extract_text_per_slide(pptx_bytes)
    slide_images = await _get_demo_slide_images(len(slide_texts))

    num = min(len(slide_images), len(slide_texts)) if slide_texts else len(slide_images)

    logger.info("Demo/translate: returning {} slides", num)
    return {
        "slide_count": num,
        "slide_texts": slide_texts[:num],
        "slide_images": slide_images[:num],
        "translated_pptx_b64": translated_pptx_b64,
        "user_prompt": user_prompt,
    }


@router.post("/screencast/demo/generate-scripts")
async def demo_generate_scripts():
    """Return demo-generated scripts parsed from the SRT file."""
    settings = get_settings()
    if not settings.demo_data:
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
async def demo_render():
    """Run the real FFmpeg pipeline with demo data (images + MP3 + SRT).

    If per-slide MP3 files exist (slide_001.mp3, ...), the full pipeline runs:
      images + audio → clips → concat → embed subtitles → faststart
    This allows testing the subtitle embedding without burning API tokens.
    Falls back to serving a pre-existing MP4 if no MP3 files are found.
    """
    settings = get_settings()
    if not settings.demo_data:
        raise HTTPException(status_code=403, detail="Demo-Modus ist nicht aktiviert")

    subtitle_data = _load_demo_subtitles()
    pptx_path = _find_demo_pptx()
    if pptx_path:
        slide_texts = _extract_text_per_slide(pptx_path.read_bytes())
    else:
        slide_texts = _load_demo_scripts()
    num_slides = len(slide_texts) or 6
    demo_audio = _load_demo_audio_files(num_slides)

    # ── Mode A: Per-slide MP3 files exist → run the full FFmpeg pipeline ──
    if demo_audio:
        slide_images_b64 = await _get_demo_slide_images(num_slides)
        logger.info("Demo/render: got {} slide images", len(slide_images_b64))

        num_slides = min(len(slide_images_b64), len(demo_audio))
        if num_slides == 0:
            raise HTTPException(status_code=404, detail="Keine Demo-Slides oder Audio")

        slide_pause = 0.5
        logger.info("Demo/render: PIPELINE mode – {} slides, {} MP3s", len(slide_images_b64), len(demo_audio))

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Write slide images to temp
            slide_image_paths: list[Path] = []
            for i, img_b64 in enumerate(slide_images_b64[:num_slides]):
                img_path = tmp / f"slide_{i:03d}.png"
                img_path.write_bytes(base64.b64decode(img_b64))
                slide_image_paths.append(img_path)

            # Copy demo MP3s to temp (so paths are clean)
            audio_paths: list[Path] = []
            for i, src in enumerate(demo_audio[:num_slides]):
                dst = tmp / f"audio_{i:03d}.mp3"
                dst.write_bytes(src.read_bytes())
                audio_paths.append(dst)

            # Create video clip per slide (image + audio)
            clip_paths: list[Path] = []
            for i in range(num_slides):
                clip_path = tmp / f"clip_{i:03d}.mp4"
                try:
                    _create_slide_video(
                        slide_image_paths[i], audio_paths[i], clip_path, pause=slide_pause
                    )
                except RuntimeError as e:
                    raise HTTPException(status_code=500, detail=str(e))
                clip_paths.append(clip_path)
                logger.info("Demo clip {}/{} done", i + 1, num_slides)

            # Concatenate
            concat_path = tmp / "concat.mp4"
            _concatenate_videos(clip_paths, concat_path)
            logger.info("Demo concat done, streams: {}", _probe_streams(concat_path))

            # Build subtitles from audio durations (like the real pipeline)
            per_slide_data = []
            for i in range(num_slides):
                dur = _get_audio_duration(audio_paths[i])
                per_slide_data.append({"alignment": None, "audio_duration": dur})
            built_subs = build_subtitles(per_slide_data, slide_pause=slide_pause)

            # Prefer file-based subtitles (from demo/slides/) over built ones
            srt_content = subtitle_data.get("srt", "") or built_subs.get("srt", "")
            final_subtitle_data = {
                "srt": subtitle_data.get("srt", "") or built_subs.get("srt", ""),
                "vtt": subtitle_data.get("vtt", "") or built_subs.get("vtt", ""),
                "txt": subtitle_data.get("txt", "") or built_subs.get("txt", ""),
                "alignment_json": built_subs.get("alignment_json", "[]"),
            }

            # Embed subtitles
            if srt_content:
                srt_path = tmp / "subtitles.srt"
                srt_path.write_text(srt_content, encoding="utf-8")
                logger.info("Demo SRT content length: {} chars", len(srt_content))
                subtitled_path = tmp / "concat_sub.mp4"
                if _embed_subtitles(concat_path, srt_path, subtitled_path):
                    concat_path = subtitled_path
                else:
                    logger.warning("Demo: subtitle embedding FAILED")
            else:
                logger.warning("Demo: no SRT data, skipping subtitle embedding")

            # Cache per-slide MP3 audio bytes
            audio_id = uuid.uuid4().hex
            _audio_cache[audio_id] = [ap.read_bytes() for ap in audio_paths[:num_slides]]
            logger.info("Demo: cached {} audio files under id={}", num_slides, audio_id)

            # Faststart
            final_path = tmp / "final.mp4"
            output_bytes = _apply_faststart(concat_path, final_path)

        logger.info("Demo/render PIPELINE complete, size={} bytes", len(output_bytes))
        subtitle_json = json.dumps(final_subtitle_data)
        subtitle_b64 = base64.b64encode(subtitle_json.encode("utf-8")).decode("ascii")
        return StreamingResponse(
            iter([output_bytes]),
            media_type="video/mp4",
            headers={
                "Content-Length": str(len(output_bytes)),
                "X-Subtitles": subtitle_b64,
                "X-Audio-Id": audio_id,
                "X-Audio-Count": str(num_slides),
            },
        )

    # ── Mode B: No MP3 files → serve pre-existing MP4 as-is ──
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
