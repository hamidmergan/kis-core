"""Screencast-Demo route: serve pre-recorded demo PPTX with fixed scripts and audio."""

import asyncio
import base64
import json
import re
import subprocess
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from src.dependencies import get_current_user
from src import database as db
from src.storage import get_job_file, save_job_file, job_file_exists, delete_job_folder

router = APIRouter(tags=["screencast-demo"])

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo"  # /app/demo in Docker


# ── Pydantic models ──────────────────────────────────────────────────────────

class DemoTranslateRequest(BaseModel):
    fast_mode: bool = False


class DemoGenerateScriptsRequest(BaseModel):
    translate_job_uuid: str | None = None
    user_prompt: str | None = None


class DemoRenderRequest(BaseModel):
    translate_job_uuid: str = ""
    dpi: int = 100


# ── Helper functions ─────────────────────────────────────────────────────────

def _load_demo_user_prompt() -> str:
    """Load user prompt from Anweisung.txt in demo/slides/."""
    prompt_path = DEMO_DIR / "slides" / "Anweisung.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return ""


def _load_demo_scripts() -> list[str]:
    """Extract per-slide scripts from the SRT file in demo/slides/."""
    import re as _re
    srt_path = DEMO_DIR / "slides" / "subtitles.srt"
    if not srt_path.exists():
        return []

    content = srt_path.read_text(encoding="utf-8")
    entries: list[tuple[float, float, str]] = []
    for block in _re.split(r"\n\n+", content.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        m = _re.match(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", lines[1])
        if not m:
            continue
        start = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 1000
        end = int(m[5]) * 3600 + int(m[6]) * 60 + int(m[7]) + int(m[8]) / 1000
        text = " ".join(lines[2:]).strip()
        entries.append((start, end, text))

    if not entries:
        return []

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
    """Load slide images from demo/slides/ as base64 strings."""
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
    """Get demo slide images with PPTX extraction and caching."""
    global _demo_images_cache

    images = _load_demo_slide_images()
    if images:
        return images

    if _demo_images_cache:
        logger.info("Using cached PPTX images ({} slides)", len(_demo_images_cache))
        return _demo_images_cache

    from src.routes.screencast import _convert_slides_to_images_async, _extract_text_per_slide

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

    pptx_path = _find_demo_pptx()
    if pptx_path:
        slide_texts = _extract_text_per_slide(pptx_path.read_bytes())[:num_slides]
    else:
        slide_texts = [f"Slide {i+1}" for i in range(num_slides)]
    logger.info("Generating {} placeholder slides", len(slide_texts))
    return await asyncio.to_thread(_generate_placeholder_slides, slide_texts)


def _generate_placeholder_slides(slide_texts: list[str]) -> list[str]:
    """Generate simple placeholder slide images using FFmpeg drawtext."""
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

    from src.routes.screencast import _pptx_to_images, _extract_text_per_slide

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


_demo_split_dir: Path | None = None


def _load_demo_audio_files(num_slides: int) -> list[Path]:
    """Load per-slide MP3 audio files from demo/slides/."""
    global _demo_split_dir

    slides_dir = DEMO_DIR / "slides"
    if not slides_dir.exists():
        return []

    for search_dir in [slides_dir, slides_dir / "Audio"]:
        per_slide = sorted(search_dir.glob("slide_*.mp3"))
        if per_slide:
            return per_slide

    if _demo_split_dir and _demo_split_dir.exists():
        cached = sorted(_demo_split_dir.glob("slide_*.mp3"))
        if len(cached) == num_slides:
            return cached

    all_mp3 = sorted(slides_dir.glob("*.mp3"))
    if not all_mp3 or num_slides < 1:
        return []

    combined_mp3 = all_mp3[0]
    logger.info("Demo: splitting combined MP3 '{}' into {} parts", combined_mp3.name, num_slides)

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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/screencast-demo/available")
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


@router.post("/screencast-demo/translate")
async def demo_translate(body: DemoTranslateRequest, current_user: dict = Depends(get_current_user)):
    """Return demo translation data (slide images, texts, translated PPTX).

    Creates a screencast_demo_render job and saves the PPTX to its folder.
    """
    global _demo_images_cache

    if db.get_setting("demo_data", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Demo-Modus ist nicht aktiviert")

    pptx_path = _find_demo_pptx()
    if not pptx_path:
        raise HTTPException(status_code=404, detail="Keine PPTX in demo/slides/ gefunden")

    from src.routes.screencast import _extract_text_per_slide, _convert_slides_to_images_async, _maybe_start_cleanup_task
    user_prompt = _load_demo_user_prompt()
    _maybe_start_cleanup_task()

    logger.info("Demo/translate: using PPTX '{}', fast_mode={}", pptx_path.name, body.fast_mode)
    pptx_bytes = pptx_path.read_bytes()

    translate_job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    db.create_job(translate_job_uuid, user_id, "screencast_demo_render", pptx_path.name)
    from src.storage import save_job_file as _save_job_file
    _save_job_file(translate_job_uuid, "translated.pptx", pptx_bytes)
    db.update_job_status(translate_job_uuid, "awaiting_user")
    db.update_job_expiry(translate_job_uuid, 168)
    logger.info("Demo/translate: created job {} with PPTX in job folder", translate_job_uuid)

    slide_texts = _extract_text_per_slide(pptx_bytes)
    if not slide_texts:
        raise HTTPException(status_code=400, detail="Keine Slides in der Präsentation gefunden")

    _save_job_file(translate_job_uuid, "scripts.txt", json.dumps(slide_texts, ensure_ascii=False).encode())
    if user_prompt:
        _save_job_file(translate_job_uuid, "prompt.txt", user_prompt.encode())

    if body.fast_mode:
        return {
            "slide_count": len(slide_texts),
            "slide_texts": slide_texts,
            "slide_images": [],
            "translate_job_uuid": translate_job_uuid,
            "user_prompt": user_prompt,
        }

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
            _demo_images_cache = slide_images_b64
            logger.info("Demo/translate: extracted {} slide images", len(slide_images_b64))
        except RuntimeError as e:
            logger.warning("Demo/translate: image extraction failed ({}), falling back to _get_demo_slide_images", e)
            slide_images_b64 = await _get_demo_slide_images(len(slide_texts))

    num = min(len(slide_images_b64), len(slide_texts))
    _save_job_file(translate_job_uuid, "slide_images.json", json.dumps(slide_images_b64[:num]).encode())

    first_size = len(slide_images_b64[0]) if slide_images_b64 else 0
    logger.info("Demo/translate returning: slide_images count={}, first_size={}", num, first_size)
    return {
        "slide_count": num,
        "slide_texts": slide_texts[:num],
        "slide_images": slide_images_b64[:num],
        "translate_job_uuid": translate_job_uuid,
        "user_prompt": user_prompt,
    }


@router.post("/screencast-demo/generate-scripts")
async def demo_generate_scripts(body: DemoGenerateScriptsRequest = DemoGenerateScriptsRequest()):
    """Return demo-generated scripts parsed from the SRT file."""
    if db.get_setting("demo_data", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Demo-Modus ist nicht aktiviert")

    if body.translate_job_uuid and re.match(r"^[a-f0-9]{32}$", body.translate_job_uuid):
        try:
            get_job_file(body.translate_job_uuid, "scripts.txt")
        except Exception:
            raise HTTPException(status_code=410, detail="Job-Daten nicht mehr verfügbar — bitte neuen Screencast starten")

    if body.translate_job_uuid and re.match(r"^[a-f0-9]{32}$", body.translate_job_uuid) and body.user_prompt is not None:
        try:
            save_job_file(body.translate_job_uuid, "prompt.txt", body.user_prompt.encode())
        except Exception:
            pass

    scripts = _load_demo_scripts()
    if not scripts:
        raise HTTPException(status_code=404, detail="Keine Demo-Skripte (subtitles.srt fehlt in demo/slides/)")

    if body.translate_job_uuid and re.match(r"^[a-f0-9]{32}$", body.translate_job_uuid):
        try:
            save_job_file(body.translate_job_uuid, "suggested_scripts.json", json.dumps(scripts, ensure_ascii=False).encode())
        except Exception:
            pass

    logger.info("Demo/generate-scripts: returning {} scripts", len(scripts))
    return {"scripts": scripts}


@router.post("/screencast-demo/render")
async def demo_render(
    body: DemoRenderRequest,
    current_user: dict = Depends(get_current_user),
):
    """Queue a demo render job (Mode A: MP3 files exist) or serve pre-existing MP4 (Mode B)."""
    if db.get_setting("demo_data", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Demo-Modus ist nicht aktiviert")

    user_id = current_user.get("user_id", 0)
    if db.has_active_job_for_tool(user_id, ["screencast_render", "screencast_auto", "screencast_demo_render"]):
        raise HTTPException(status_code=409, detail="Du hast bereits einen laufenden Screencast-Render-Job.")

    from src.routes.screencast import _extract_text_per_slide
    pptx_path = _find_demo_pptx()
    if pptx_path:
        slide_texts = _extract_text_per_slide(pptx_path.read_bytes())
    else:
        slide_texts = _load_demo_scripts()
    num_slides_hint = len(slide_texts) or 6
    demo_audio = _load_demo_audio_files(num_slides_hint)

    # ── Mode A: MP3 files exist → queue Celery task ──
    if demo_audio:
        if not body.translate_job_uuid:
            raise HTTPException(status_code=400, detail="translate_job_uuid fehlt")
        translate_job = db.get_job(body.translate_job_uuid)
        if not translate_job:
            raise HTTPException(status_code=404, detail="Job nicht gefunden")
        if translate_job["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Job")
        if not job_file_exists(body.translate_job_uuid, "translated.pptx"):
            delete_job_folder(body.translate_job_uuid)
            db.delete_job(body.translate_job_uuid)
            raise HTTPException(status_code=404, detail="Job-Dateien nicht mehr vorhanden. Bitte Demo neu starten.")

        from src.tasks.screencast_tasks import run_screencast_demo_render
        task = run_screencast_demo_render.apply_async(args=[body.translate_job_uuid, body.dpi])
        db.set_job_celery_task_id(body.translate_job_uuid, task.id)
        db.set_render_queued_at(body.translate_job_uuid)
        db.update_job_status(body.translate_job_uuid, "running")

        logger.info("Demo render job queued: job_uuid={}", body.translate_job_uuid)
        return {"job_uuid": body.translate_job_uuid}

    # ── Mode B: No MP3 files → serve pre-existing MP4 ──
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
    return StreamingResponse(
        iter([video_bytes]),
        media_type="video/mp4",
        headers={
            "Content-Length": str(len(video_bytes)),
        },
    )
