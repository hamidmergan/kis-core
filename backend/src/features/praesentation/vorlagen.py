# backend/src/features/praesentation/vorlagen.py
"""Own templates of a person, and the one the system ships."""

from __future__ import annotations

import functools
import json
import zipfile
from io import BytesIO
from pathlib import Path

from loguru import logger

from src.features.praesentation import bau, vorlage, vorlagen_repo, vorschau
from src.features.praesentation.schemas import SYSTEM_VORLAGE, Slide
from src.features.praesentation.vorlage import Analyse
from src.limits import PRAESENTATION_TEMPLATE_MAX_MB
from src.storage import delete_key_file, get_key_file, key_file_exists, save_key_file

ASSETS = Path(__file__).parent / "assets"
ERLAUBT = (".pptx", ".potx")
MAX_BYTES = PRAESENTATION_TEMPLATE_MAX_MB * 1024 * 1024


class VorlageUnbrauchbar(ValueError):
    """The upload is refused, the key names the reason for the person."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def systemvorlage() -> tuple[bytes, dict]:
    meta = json.loads((ASSETS / "thl.json").read_text("utf8"))
    return (ASSETS / "thl.pptx").read_bytes(), {"name": meta["name"], "style_text": meta["style_text"]}


@functools.lru_cache(maxsize=1)
def system_analyse() -> Analyse:
    """The THL template never changes at runtime, so its analysis is worth caching."""
    return vorlage.analysiere(systemvorlage()[0])


def hat_makros(data: bytes) -> bool:
    with zipfile.ZipFile(BytesIO(data)) as z:
        return any(n.lower().endswith("vbaproject.bin") for n in z.namelist())


def als_pptx(data: bytes) -> bytes:
    """A potx is a pptx with another content type, the rest is the same."""
    out = BytesIO()
    with zipfile.ZipFile(BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for n in src.namelist():
            b = src.read(n)
            if n == "[Content_Types].xml":
                b = b.replace(b"presentationml.template.main+xml", b"presentationml.presentation.main+xml")
            dst.writestr(n, b)
    return out.getvalue()


def pruefe(data: bytes, ext: str) -> tuple[bytes, Analyse]:
    """The file as pptx bytes plus its analysis, or the reason it cannot be used."""
    if ext not in ERLAUBT:
        raise VorlageUnbrauchbar("praesentation.templateFormat")
    if len(data) > MAX_BYTES:
        raise VorlageUnbrauchbar("praesentation.templateTooBig")
    try:
        if hat_makros(data):
            raise VorlageUnbrauchbar("praesentation.templateMacros")
        if ext == ".potx":
            data = als_pptx(data)
        analyse = vorlage.analysiere(data)
    except VorlageUnbrauchbar:
        raise
    except Exception as exc:
        raise VorlageUnbrauchbar("praesentation.templateBroken") from exc
    if not analyse.layouts or not any(l.rolle for l in analyse.layouts):
        raise VorlageUnbrauchbar("praesentation.templateNoLayouts")
    return data, analyse


def deckblatt_vorschau(data: bytes, analyse: Analyse, name: str) -> bytes:
    deck = bau.baue(data, analyse, [Slide(id="s1", role="deckblatt", title=name)], {}, name, False)
    bilder = vorschau.render(deck)
    if not bilder:
        raise RuntimeError("keine Vorschau")
    return bilder[0]


@functools.lru_cache(maxsize=1)
def system_cover_vorschau() -> bytes:
    """The THL cover preview never changes at runtime, so it is worth rendering only once per process."""
    data, meta = systemvorlage()
    return deckblatt_vorschau(data, system_analyse(), meta["name"])


def vorlage_key(user_id: int, vid: str) -> str:
    return f"users/{user_id}/praesentation/vorlagen/{vid}.pptx"


def vorschau_key(user_id: int, vid: str) -> str:
    return f"users/{user_id}/praesentation/vorlagen/{vid}.png"


def meta_key(user_id: int, vid: str) -> str:
    return f"users/{user_id}/praesentation/vorlagen/{vid}.json"


def speichere(user_id: int, vid: str, data: bytes, vorschau_png: bytes | None, meta: dict | None = None) -> None:
    save_key_file(vorlage_key(user_id, vid), data)
    if vorschau_png:
        save_key_file(vorschau_key(user_id, vid), vorschau_png)
    if meta is not None:
        save_key_file(meta_key(user_id, vid), json.dumps(meta, ensure_ascii=False).encode())


def lade(user_id: int, vid: str) -> bytes | None:
    key = vorlage_key(user_id, vid)
    try:
        return get_key_file(key) if key_file_exists(key) else None
    except Exception:
        return None


def lade_vorschau(user_id: int, vid: str) -> bytes | None:
    key = vorschau_key(user_id, vid)
    try:
        return get_key_file(key) if key_file_exists(key) else None
    except Exception:
        return None


def lade_meta(user_id: int, vid: str) -> dict | None:
    """The cached roles/hasImages of a saved template, so a listing never re-analyses the file."""
    key = meta_key(user_id, vid)
    try:
        return json.loads(get_key_file(key)) if key_file_exists(key) else None
    except Exception:
        return None


def loesche(user_id: int, vid: str) -> None:
    for key in (vorlage_key(user_id, vid), vorschau_key(user_id, vid), meta_key(user_id, vid)):
        try:
            delete_key_file(key)
        except Exception:
            pass


def _touch_best_effort(vid: str) -> None:
    """Bump last_used_at, but a write failure here must never sink a valid template."""
    try:
        vorlagen_repo.touch(vid)
    except Exception as exc:
        logger.warning("Vorlage {} konnte nicht beruehrt werden: {}", vid, exc)


def aufloesen(user_id: int, template_id: str) -> tuple[bytes, Analyse, dict, bool]:
    """The chosen template, or the system one with a flag when the own one cannot be read."""
    if template_id and template_id != SYSTEM_VORLAGE:
        zeile = vorlagen_repo.get(user_id, template_id)
        data = lade(user_id, template_id) if zeile else None
        if zeile and data:
            try:
                analyse = vorlage.analysiere(data)
            except Exception as exc:
                logger.warning("Vorlage {} unlesbar, THL springt ein: {}", template_id, exc)
            else:
                _touch_best_effort(template_id)
                return data, analyse, {"name": zeile["name"], "style_text": zeile["stiltext"]}, False
        data, meta = systemvorlage()
        return data, vorlage.analysiere(data), meta, True
    data, meta = systemvorlage()
    return data, vorlage.analysiere(data), meta, False
