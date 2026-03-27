"""Screencast-Demo route: static playthrough using pre-baked demo files.

No computation, no Celery tasks, no PPTX parsing.
Files are read from S3 under the 'demo/' prefix (production) or from
backend/demo/ on the local filesystem when DEMO_LOCAL=true:
  demo/images/slide_001.png ...  → slide images
  demo/accepted_scripts.json     → scripts per slide (list[str])
  demo/output.mp4                → pre-rendered video
"""

import base64
import io
import json
import os
import zipfile
from pathlib import Path

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from src.dependencies import get_current_user
from src.limits import BUNDLE_INCLUDE_AUDIO, BUNDLE_INCLUDE_IMAGES
from src.storage import _S3_BUCKET, _s3

router = APIRouter(tags=["screencast-demo"])

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo"
_S3_DEMO_PREFIX = "demo"

# DEMO_LOCAL=true  → liest aus backend/demo/ (lokal)
# DEMO_LOCAL=false / nicht gesetzt → liest aus S3 demo/-Prefix (Server)
DEMO_LOCAL = os.environ.get("DEMO_LOCAL", "false").lower() == "true"


# ── Pydantic models ──────────────────────────────────────────────────────────

class DemoTranslateRequest(BaseModel):
    fast_mode: bool = False


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
    provider: str = "kokoro"


# ── S3 helpers ────────────────────────────────────────────────────────────────

def _s3_get(key: str) -> bytes | None:
    try:
        resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
        return resp["Body"].read()
    except ClientError:
        return None


def _s3_exists(key: str) -> bool:
    try:
        _s3().head_object(Bucket=_S3_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def _s3_list_keys(prefix: str) -> list[str]:
    resp = _s3().list_objects_v2(Bucket=_S3_BUCKET, Prefix=prefix)
    return [obj["Key"] for obj in resp.get("Contents", [])]


# ── Helper functions ─────────────────────────────────────────────────────────

def _require_demo_enabled() -> None:
    pass


def _load_accepted_scripts() -> list[str]:
    """Load scripts from accepted_scripts.json or render_scripts.json."""
    for fname in ("accepted_scripts.json", "render_scripts.json"):
        if not DEMO_LOCAL:
            data_bytes = _s3_get(f"{_S3_DEMO_PREFIX}/{fname}")
            if data_bytes is None:
                continue
            data = json.loads(data_bytes.decode("utf-8"))
        else:
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
    if not DEMO_LOCAL:
        prefix = f"{_S3_DEMO_PREFIX}/images/"
        keys = sorted(k for k in _s3_list_keys(prefix) if k.endswith(".png"))
        result = []
        for key in keys:
            data = _s3_get(key)
            if data:
                result.append(base64.b64encode(data).decode())
        return result

    images_dir = DEMO_DIR / "images"
    if not images_dir.exists():
        return []
    images = sorted(images_dir.glob("slide_*.png"))
    if not images:
        images = sorted(images_dir.glob("*.png"))
    return [base64.b64encode(img.read_bytes()).decode() for img in images]


def _find_demo_video() -> str | Path | None:
    """Return S3 key or local Path for the pre-rendered demo video."""
    if not DEMO_LOCAL:
        for name in ("output.mp4", "video.mp4"):
            key = f"{_S3_DEMO_PREFIX}/{name}"
            if _s3_exists(key):
                return key
        keys = sorted(k for k in _s3_list_keys(f"{_S3_DEMO_PREFIX}/") if k.endswith(".mp4"))
        return keys[0] if keys else None

    for name in ("output.mp4", "video.mp4"):
        p = DEMO_DIR / name
        if p.exists():
            return p
    mp4s = sorted(DEMO_DIR.glob("*.mp4"))
    return mp4s[0] if mp4s else None


def _demo_images_exist() -> bool:
    if not DEMO_LOCAL:
        prefix = f"{_S3_DEMO_PREFIX}/images/"
        keys = [k for k in _s3_list_keys(prefix) if k.endswith(".png")]
        return bool(keys)
    images_dir = DEMO_DIR / "images"
    return images_dir.exists() and bool(list(images_dir.glob("*.png")))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/screencast-demo/available")
async def demo_available():
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
async def demo_translate(body: DemoTranslateRequest, _: dict = Depends(get_current_user)):
    """Return demo slide data instantly from pre-baked files."""
    _require_demo_enabled()

    scripts = _load_accepted_scripts()
    if not scripts:
        raise HTTPException(
            status_code=404,
            detail="Keine Skripte in demo/ gefunden (accepted_scripts.json fehlt)",
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
async def demo_generate_scripts(body: DemoGenerateScriptsRequest = DemoGenerateScriptsRequest()):
    """Return pre-baked scripts instantly."""
    _require_demo_enabled()

    scripts = _load_accepted_scripts()
    if not scripts:
        raise HTTPException(
            status_code=404,
            detail="Keine Skripte in demo/ gefunden (accepted_scripts.json fehlt)",
        )

    logger.info("Demo/generate-scripts: returning {} scripts", len(scripts))
    return {"scripts": scripts}


@router.post("/screencast-demo/render")
async def demo_render(body: DemoRenderRequest, _: dict = Depends(get_current_user)):
    """Stream the pre-rendered demo video directly."""
    _require_demo_enabled()

    video = _find_demo_video()
    if not video:
        raise HTTPException(
            status_code=404,
            detail="Kein Demo-Video gefunden (output.mp4 fehlt in demo/)",
        )

    if not DEMO_LOCAL:
        video_bytes = _s3_get(str(video))
        if not video_bytes:
            raise HTTPException(status_code=404, detail="Demo-Video konnte nicht aus S3 gelesen werden")
        name = str(video).split("/")[-1]
    else:
        video_bytes = Path(video).read_bytes()
        name = Path(video).name

    logger.info("Demo/render: streaming {} ({} bytes)", name, len(video_bytes))
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
        data = filepath.read_bytes()
        return _add_bytes_and_yield(arcname, data)

    # Video
    video = _find_demo_video()
    if video:
        if not DEMO_LOCAL:
            data = _s3_get(str(video))
            if data:
                yield _add_bytes_and_yield(str(video).split("/")[-1], data)
                del data
        else:
            yield _add_file_and_yield(Path(video).name, Path(video))

    # Script JSON
    for fname in ("accepted_scripts.json", "render_scripts.json"):
        if not DEMO_LOCAL:
            data = _s3_get(f"{_S3_DEMO_PREFIX}/{fname}")
            if data:
                yield _add_bytes_and_yield(fname, data)
                break
        else:
            p = DEMO_DIR / fname
            if p.exists():
                yield _add_file_and_yield(fname, p)
                break

    # PPTX, audio, images
    if not DEMO_LOCAL:
        for key in sorted(k for k in _s3_list_keys(f"{_S3_DEMO_PREFIX}/") if k.endswith(".pptx")):
            data = _s3_get(key)
            if data:
                yield _add_bytes_and_yield(key.split("/")[-1], data)
        if BUNDLE_INCLUDE_AUDIO:
            for key in sorted(_s3_list_keys(f"{_S3_DEMO_PREFIX}/audio/")):
                data = _s3_get(key)
                if data:
                    yield _add_bytes_and_yield(f"audio/{key.split('/')[-1]}", data)
        if BUNDLE_INCLUDE_IMAGES:
            for key in sorted(k for k in _s3_list_keys(f"{_S3_DEMO_PREFIX}/images/") if k.endswith(".png")):
                data = _s3_get(key)
                if data:
                    yield _add_bytes_and_yield(f"images/{key.split('/')[-1]}", data)
    else:
        for p in sorted(DEMO_DIR.glob("*.pptx")):
            yield _add_file_and_yield(p.name, p)
        if BUNDLE_INCLUDE_AUDIO:
            audio_dir = DEMO_DIR / "audio"
            if audio_dir.exists():
                for f in sorted(audio_dir.iterdir()):
                    if f.is_file():
                        yield _add_file_and_yield(f"audio/{f.name}", f)
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
async def demo_bundle(_: dict = Depends(get_current_user)):
    """Return a ZIP with the demo video and audio files."""
    _require_demo_enabled()

    return StreamingResponse(
        _streaming_demo_bundle(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="screencast_demo_bundle.zip"',
        },
    )
