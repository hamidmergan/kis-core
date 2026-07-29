"""Screencast-Demo route: static playthrough using pre-baked demo files.

No computation, no Celery tasks, no PPTX parsing. All files are read from
backend/demo/ on the local filesystem (mounted into the container at
/app/demo, read-only):
  demo/images/slide_*.png        → slide images
  demo/accepted_scripts.json     → scripts per slide (list[str])
  demo/output.mp4                → pre-rendered video
  demo/audio/*.mp3, demo/*.pptx  → extras for the bundle download
"""

import base64
import io
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from src.dependencies import get_current_user
from src.dependencies_rbac import require_tool_access
from src.i18n import get_locale, t
from src.limits import BUNDLE_INCLUDE_AUDIO, BUNDLE_INCLUDE_IMAGES

router = APIRouter(
    tags=["screencast-demo"],
    dependencies=[Depends(require_tool_access("screencast"))],
)

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo"


# ── Pydantic models ──────────────────────────────────────────────────────────

class DemoGenerateScriptsRequest(BaseModel):
    translate_job_uuid: str | None = None
    user_prompt: str | None = None


class DemoRenderRequest(BaseModel):
    translate_job_uuid: str = ""
    dpi: int = 100
    speed: float = 1.0
    slide_pause: float = 0.5
    voice_id: str = ""
    voice_label: str = ""
    provider_id: int = 0


# ── Helper functions ─────────────────────────────────────────────────────────

def _load_accepted_scripts() -> list[str]:
    """Load scripts from accepted_scripts.json or render_scripts.json."""
    for fname in ("accepted_scripts.json", "render_scripts.json"):
        path = DEMO_DIR / fname
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue
        result: list[str] = []
        for item in data:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                for key in ("script", "text", "content"):
                    if key in item:
                        result.append(str(item[key]))
                        break
        if result:
            return result
    return []


def _load_demo_images() -> list[str]:
    """Load slide images from demo/images/ as base64 strings."""
    images_dir = DEMO_DIR / "images"
    if not images_dir.exists():
        return []
    images = sorted(images_dir.glob("slide_*.png"))
    if not images:
        images = sorted(images_dir.glob("*.png"))
    return [base64.b64encode(img.read_bytes()).decode() for img in images]


def _find_demo_video() -> Path | None:
    """Return local Path for the pre-rendered demo video."""
    for name in ("output.mp4", "video.mp4"):
        p = DEMO_DIR / name
        if p.exists():
            return p
    mp4s = sorted(DEMO_DIR.glob("*.mp4"))
    return mp4s[0] if mp4s else None


def _demo_images_exist() -> bool:
    images_dir = DEMO_DIR / "images"
    return images_dir.exists() and bool(list(images_dir.glob("*.png")))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/screencast-demo/available")
def demo_available():
    """Check whether demo data is available."""
    images_exist = _demo_images_exist()
    video_path = _find_demo_video()
    return {
        "available": images_exist,
        "has_video": video_path is not None,
        "demo_data_enabled": True,
        "pptx_exists": images_exist,
        "video_exists": video_path is not None,
    }


@router.post("/screencast-demo/translate")
def demo_translate(
    _: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Return demo slide data instantly from pre-baked files."""
    scripts = _load_accepted_scripts()
    if not scripts:
        raise HTTPException(
            status_code=404,
            detail=t("screencastDemo.scriptsMissing", locale),
        )

    images = _load_demo_images()
    logger.info("Demo/translate: {} slides, {} images", len(scripts), len(images))

    return {
        "slide_count": len(scripts),
        "slide_texts": scripts,
        "slide_images": images,
        "translate_job_uuid": "demo",
        "user_prompt": "",
    }


@router.post("/screencast-demo/generate-scripts")
def demo_generate_scripts(
    body: DemoGenerateScriptsRequest = DemoGenerateScriptsRequest(),
    locale: str = Depends(get_locale),
):
    """Return pre-baked scripts instantly."""
    scripts = _load_accepted_scripts()
    if not scripts:
        raise HTTPException(
            status_code=404,
            detail=t("screencastDemo.scriptsMissing", locale),
        )

    logger.info("Demo/generate-scripts: returning {} scripts", len(scripts))
    return {"scripts": scripts}


@router.post("/screencast-demo/render")
def demo_render(
    body: DemoRenderRequest,
    _: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Stream the pre-rendered demo video directly from disk."""
    video = _find_demo_video()
    if not video:
        raise HTTPException(
            status_code=404,
            detail=t("screencastDemo.videoMissing", locale),
        )

    video_bytes = video.read_bytes()
    logger.info("Demo/render: streaming {} ({} bytes)", video.name, len(video_bytes))
    return StreamingResponse(
        iter([video_bytes]),
        media_type="video/mp4",
        headers={"Content-Length": str(len(video_bytes))},
    )


class _ZipStreamWriter:
    """File-like object for streaming ZIP construction."""

    def __init__(self):
        self._buf = io.BytesIO()

    def write(self, data: bytes) -> int:
        return self._buf.write(data)

    def flush(self):
        pass

    def tell(self) -> int:
        return self._buf.tell()

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._buf.seek(offset, whence)

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def close(self):
        pass


def _streaming_demo_bundle():
    """Generator that yields ZIP data file-by-file for the demo bundle."""
    import zipfile as zf_mod

    stream = _ZipStreamWriter()
    zf = zf_mod.ZipFile(stream, mode="w", compression=zf_mod.ZIP_STORED)

    def _add_bytes_and_yield(arcname: str, data: bytes):
        pos_before = stream.tell()
        zf.writestr(arcname, data)
        pos_after = stream.tell()
        stream.seek(pos_before)
        return stream.read(pos_after - pos_before)

    def _add_file_and_yield(arcname: str, filepath: Path):
        return _add_bytes_and_yield(arcname, filepath.read_bytes())

    # Video
    video = _find_demo_video()
    if video:
        yield _add_file_and_yield(video.name, video)

    # Script JSON
    for fname in ("accepted_scripts.json", "render_scripts.json"):
        p = DEMO_DIR / fname
        if p.exists():
            yield _add_file_and_yield(fname, p)
            break

    # PPTX
    for p in sorted(DEMO_DIR.glob("*.pptx")):
        yield _add_file_and_yield(p.name, p)

    # Audio
    if BUNDLE_INCLUDE_AUDIO:
        audio_dir = DEMO_DIR / "audio"
        if audio_dir.exists():
            for f in sorted(audio_dir.iterdir()):
                if f.is_file():
                    yield _add_file_and_yield(f"audio/{f.name}", f)

    # Images
    if BUNDLE_INCLUDE_IMAGES:
        images_dir = DEMO_DIR / "images"
        if images_dir.exists():
            for f in sorted(images_dir.glob("*.png")):
                yield _add_file_and_yield(f"images/{f.name}", f)

    # Finalize ZIP (central directory)
    pos_before = stream.tell()
    zf.close()
    pos_after = stream.tell()
    stream.seek(pos_before)
    yield stream.read(pos_after - pos_before)


@router.get("/screencast-demo/bundle")
def demo_bundle(_: dict = Depends(get_current_user)):
    """Return a ZIP with the demo video, scripts, PPTX, audio and images."""
    return StreamingResponse(
        _streaming_demo_bundle(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="screencast_demo_bundle.zip"',
        },
    )
