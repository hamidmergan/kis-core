"""Screencast route: translate DE PPTX → EN, extract text per slide, TTS, slide images, FFmpeg → MP4."""

import asyncio
import base64
import json
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pydantic import BaseModel

from src.dependencies import get_deepl_client, get_settings
from src.services.elevenlabs_client import ElevenLabsClient
from src.services.kisski_client import KisskiClient
from src.services.glossary import GlossaryService
from src.services.translation import TranslationService
from src.translators.pptx import translate_pptx
from src.utils.file_validation import (
    MAX_OUTPUT_VIDEO_BYTES,
    MAX_SCREENCAST_SLIDES,
    MAX_UPLOAD_BYTES,
    SCREENCAST_EXTENSIONS,
)

router = APIRouter(tags=["screencast"])


# ── Pydantic models for step-by-step endpoints ──────────────────────────────

class ExtractTextsRequest(BaseModel):
    pptx_b64: str


class GenerateScriptsRequest(BaseModel):
    slide_texts: list[str]
    user_prompt: str | None = None


class PrepareRequest(BaseModel):
    translated_pptx_b64: str


class RenderRequest(BaseModel):
    scripts: list[str]
    translated_pptx_b64: str
    slide_images_b64: list[str]
    speed: float = 0.9
    slide_pause: float = 0.5


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


def _get_elevenlabs_client() -> ElevenLabsClient:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise HTTPException(status_code=500, detail="ElevenLabs API Key fehlt")
    return ElevenLabsClient(settings.elevenlabs_api_key)


def _get_kisski_client() -> KisskiClient:
    settings = get_settings()
    if not settings.kisski_api_key:
        raise HTTPException(status_code=500, detail="KISSKI API Key fehlt")
    return KisskiClient(
        api_key=settings.kisski_api_key,
        base_url=settings.kisski_base_url,
        model=settings.kisski_model,
    )


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


def _pptx_to_images(pptx_path: Path, output_dir: Path) -> list[Path]:
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
        "pdftoppm", "-png", "-r", "150",
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


def _create_slide_video(image_path: Path, audio_path: Path, output_path: Path, pause: float = 0.0) -> None:
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


def _apply_faststart(input_path: Path, output_path: Path) -> bytes:
    """Apply faststart to MP4 for web streaming."""
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-c", "copy", "-movflags", "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.warning("faststart fix failed, returning raw file: {}", result.stderr[:200])
        return input_path.read_bytes()
    return output_path.read_bytes()


async def _generate_all_scripts(
    slide_texts: list[str],
    kisski_client: KisskiClient,
    user_prompt: str | None = None,
) -> list[str]:
    """Generate spoken scripts for all slides in a single KISSKI call."""
    try:
        scripts = await asyncio.to_thread(
            kisski_client.generate_scripts_batch, slide_texts, user_prompt
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
) -> list[Path]:
    """Generate TTS audio for all slides in parallel via ElevenLabs."""
    sem = asyncio.Semaphore(5)
    audio_paths: list[Path] = [tmp / f"slide_{i:03d}.mp3" for i in range(len(slide_scripts))]

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
                mp3_bytes = await asyncio.to_thread(
                    tts_client.synthesize, script_text, "EN", speed=speed
                )
                audio_path.write_bytes(mp3_bytes)
                logger.info("TTS for slide {}/{} done", i + 1, len(slide_scripts))
            except Exception as e:
                logger.error("TTS failed for slide {}: {}", i + 1, e)
                raise HTTPException(
                    status_code=502,
                    detail=f"TTS-Fehler bei Folie {i + 1}: {e}",
                )

    await asyncio.gather(*[_tts(i, t) for i, t in enumerate(slide_scripts)])
    return audio_paths


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
    service = _build_service(glossary_json)
    settings = get_settings()
    try:
        translated_bytes = translate_pptx(pptx_bytes, settings.source_lang, settings.effective_target_lang, service)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Übersetzungsfehler: {e}")

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
        kisski_client = _get_kisski_client()
        try:
            slide_scripts, slide_images = await asyncio.gather(
                _generate_all_scripts(slide_texts, kisski_client),
                _convert_slides_to_images_async(translated_pptx_path, img_dir),
            )
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

        # PARALLELIZED
        # ── Step 4: TTS per slide ─────────────────────────────────────────
        logger.info("Step 4: Generating TTS audio per slide (parallel)")
        tts_client = _get_elevenlabs_client()
        audio_paths = await _generate_all_tts(slide_scripts, tts_client, tmp, speed)

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
    service = _build_service(glossary_json)
    settings = get_settings()
    try:
        translated_bytes = translate_pptx(
            pptx_bytes, settings.source_lang, settings.effective_target_lang, service
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Übersetzungsfehler: {e}")

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

    kisski_client = _get_kisski_client()

    # PARALLELIZED
    scripts = await _generate_all_scripts(
        body.slide_texts, kisski_client, user_prompt=body.user_prompt
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

        # Decode slide images from base64 (provided by /translate step)
        slide_images: list[Path] = []
        for i, img_b64 in enumerate(body.slide_images_b64):
            img_path = tmp / f"slide_{i:03d}.png"
            img_path.write_bytes(base64.b64decode(img_b64))
            slide_images.append(img_path)

        # Generate TTS audio
        tts_client = _get_elevenlabs_client()
        audio_paths = await _generate_all_tts(body.scripts, tts_client, tmp, body.speed)

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
                _create_slide_video(slide_images[i], audio_paths[i], clip_path, pause=body.slide_pause)
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

    return StreamingResponse(
        iter([output_bytes]),
        media_type="video/mp4",
        headers={
            "Content-Disposition": 'attachment; filename="screencast_EN.mp4"',
            "Content-Length": str(len(output_bytes)),
            "Accept-Ranges": "bytes",
        },
    )
