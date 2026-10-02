"""A prepared run from files, without compute and without jobs.

The files come from scripts/screencast_demo_bauen.py: one folder per language with
slides, scripts, deck, video and audio of the run, and in vergleich/ a shorter version
voiced by every service of stimmen.json.
"""

import base64
import io
import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from loguru import logger

from src.dependencies import get_current_user
from src.dependencies_rbac import require_tool_access
from src.i18n import get_locale, t
from src.limits import BUNDLE_INCLUDE_AUDIO, BUNDLE_INCLUDE_IMAGES

router = APIRouter(
    tags=["screencast-demo"],
    dependencies=[Depends(require_tool_access("screencast"))],
)

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo" / "screencast"
STANDARD_SPRACHE = "de"
_KENNUNG = re.compile(r"^[a-z0-9]+$")


# ── Helper functions ─────────────────────────────────────────────────────────

def _stimmen() -> list[dict]:
    """The voice services in their order, as stimmen.json lists them."""
    pfad = DEMO_DIR / "stimmen.json"
    if not pfad.exists():
        return []
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    return [s for s in daten if isinstance(s, dict) and _KENNUNG.match(str(s.get("id", "")))]


def _ordner(sprache: str) -> Path:
    """The folder of a language, the standard language when it has none."""
    if _KENNUNG.match(sprache) and (DEMO_DIR / sprache).is_dir():
        return DEMO_DIR / sprache
    return DEMO_DIR / STANDARD_SPRACHE


def _video(ordner: Path) -> Path | None:
    pfad = ordner / "video.mp4"
    return pfad if pfad.exists() else None


def _toene(ordner: Path) -> list[Path]:
    return sorted((ordner / "ton").glob("folie_*.mp3"))


def _liste(pfad: Path) -> list[str]:
    if not pfad.exists():
        return []
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    return [str(x) for x in daten] if isinstance(daten, list) else []


def _skripte(ordner: Path, locale: str) -> list[str]:
    skripte = _liste(ordner / "accepted_scripts.json")
    if not skripte:
        raise HTTPException(status_code=404, detail=t("screencastDemo.scriptsMissing", locale))
    return skripte


def _praesentation(ordner: Path) -> Path | None:
    dateien = sorted(ordner.glob("*.pptx"))
    return dateien[0] if dateien else None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/screencast-demo/available")
def demo_available():
    """Check whether demo data is available."""
    ordner = _ordner(STANDARD_SPRACHE)
    bilder = any((ordner / "folien").glob("folie_*.png"))
    video = _video(ordner) is not None
    return {
        "available": bilder,
        "has_video": video,
        "demo_data_enabled": True,
        "pptx_exists": bilder,
        "video_exists": video,
    }


@router.get("/screencast-demo/stimmen")
def demo_stimmen(_: dict = Depends(get_current_user)):
    """The voice services in their order, with the languages a comparison video exists for."""
    sprachen = sorted(p.name for p in DEMO_DIR.iterdir() if p.is_dir()) if DEMO_DIR.is_dir() else []
    return {"stimmen": [
        {
            "id": s["id"],
            "anbieter": s.get("anbieter", s["id"]),
            "eigen": bool(s.get("eigen")),
            "stimmen": {sprache: (s.get("sprachen", {}).get(sprache) or {}).get("name", "") for sprache in sprachen},
            "kennungen": {sprache: (s.get("sprachen", {}).get(sprache) or {}).get("stimme", "") for sprache in sprachen},
            "videos": [sprache for sprache in sprachen if (DEMO_DIR / sprache / "vergleich" / f"{s['id']}.mp4").exists()],
        }
        for s in _stimmen()
    ]}


@router.post("/screencast-demo/translate")
def demo_translate(
    sprache: str = STANDARD_SPRACHE,
    _: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The slides of the language as text and image, straight from the files."""
    ordner = _ordner(sprache)
    skripte = _skripte(ordner, locale)
    texte = _liste(ordner / "folientexte.json")
    bilder = [base64.b64encode(p.read_bytes()).decode() for p in sorted((ordner / "folien").glob("folie_*.png"))]
    logger.info("Demo/translate: {} slides, {} images ({})", len(skripte), len(bilder), ordner.name)
    return {
        "slide_count": len(skripte),
        "slide_texts": texte if len(texte) == len(skripte) else skripte,
        "slide_images": bilder,
        "translate_job_uuid": "demo",
        "user_prompt": "",
    }


@router.post("/screencast-demo/generate-scripts")
def demo_generate_scripts(sprache: str = STANDARD_SPRACHE, locale: str = Depends(get_locale)):
    """The prepared scripts of the language, which are the speaker notes of the deck."""
    return {"scripts": _skripte(_ordner(sprache), locale)}


@router.get("/screencast-demo/video")
def demo_video(
    sprache: str = STANDARD_SPRACHE,
    download: bool = False,
    _: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The prepared video as a file, so the player can seek."""
    video = _video(_ordner(sprache))
    if not video:
        raise HTTPException(status_code=404, detail=t("screencastDemo.videoMissing", locale))
    return FileResponse(
        video,
        media_type="video/mp4",
        filename="screencast_demo.mp4" if download else None,
        content_disposition_type="attachment" if download else "inline",
    )


@router.get("/screencast-demo/vergleich/{sprache}/{anbieter}")
def demo_vergleich(sprache: str, anbieter: str, _: dict = Depends(get_current_user)):
    """The shorter version voiced by one service, for the comparison below the result."""
    if anbieter not in {s["id"] for s in _stimmen()} or not _KENNUNG.match(sprache):
        raise HTTPException(status_code=404)
    pfad = DEMO_DIR / sprache / "vergleich" / f"{anbieter}.mp4"
    if not pfad.exists():
        raise HTTPException(status_code=404)
    return FileResponse(pfad, media_type="video/mp4")


@router.get("/screencast-demo/vorschau/{index}")
def demo_vorschau(index: int, sprache: str = STANDARD_SPRACHE, _: dict = Depends(get_current_user)):
    """The audio of one slide for the preview while the demo renders."""
    toene = _toene(_ordner(sprache))
    if not 0 <= index < len(toene):
        raise HTTPException(status_code=404)
    return FileResponse(toene[index], media_type="audio/mpeg")


@router.get("/screencast-demo/pptx")
def demo_pptx(sprache: str = STANDARD_SPRACHE, _: dict = Depends(get_current_user)):
    """The presentation in the language, translated where needed."""
    datei = _praesentation(_ordner(sprache))
    if not datei:
        raise HTTPException(status_code=404)
    return FileResponse(
        datei,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=datei.name,
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


def _streaming_demo_bundle(ordner: Path):
    """Generator that yields ZIP data file-by-file for the demo bundle."""
    import zipfile as zf_mod

    stream = _ZipStreamWriter()
    zf = zf_mod.ZipFile(stream, mode="w", compression=zf_mod.ZIP_STORED)

    def _add_file_and_yield(arcname: str, filepath: Path):
        pos_before = stream.tell()
        zf.writestr(arcname, filepath.read_bytes())
        pos_after = stream.tell()
        stream.seek(pos_before)
        return stream.read(pos_after - pos_before)

    video = _video(ordner)
    if video:
        yield _add_file_and_yield("screencast.mp4", video)
    skripte = ordner / "accepted_scripts.json"
    if skripte.exists():
        yield _add_file_and_yield(skripte.name, skripte)
    praesentation = _praesentation(ordner)
    if praesentation:
        yield _add_file_and_yield(praesentation.name, praesentation)
    if BUNDLE_INCLUDE_AUDIO:
        for f in _toene(ordner):
            yield _add_file_and_yield(f"audio/{f.name}", f)
    if BUNDLE_INCLUDE_IMAGES:
        for f in sorted((ordner / "folien").glob("folie_*.png")):
            yield _add_file_and_yield(f"images/{f.name}", f)

    # Finalize ZIP (central directory)
    pos_before = stream.tell()
    zf.close()
    pos_after = stream.tell()
    stream.seek(pos_before)
    yield stream.read(pos_after - pos_before)


@router.get("/screencast-demo/bundle")
def demo_bundle(sprache: str = STANDARD_SPRACHE, _: dict = Depends(get_current_user)):
    """Return a ZIP with the video, the scripts and the presentation."""
    return StreamingResponse(
        _streaming_demo_bundle(_ordner(sprache)),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="screencast_demo_bundle.zip"',
        },
    )
