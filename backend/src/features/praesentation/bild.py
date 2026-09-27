"""Image size from a placeholder and the call to the image provider."""

from __future__ import annotations

import base64
import re

from src.tasks.general_tasks import _image_http_client

# The pixels follow the field at print resolution, a floor so a stamp-sized field still gets a usable
# picture, a ceiling so a full-width banner does not cost minutes of generation time.
EMU_JE_ZOLL = 914400
ZIEL_DPI = 300
LANGE_SEITE_MIN = 768
LANGE_SEITE_MAX = 1920
_MINDEST = 256
_RUECKFALL = "1024x1024"


def bildgroesse(width: int, height: int) -> str:
    """The field at 300 dpi, the long side capped both ways, both sides multiples of 16."""
    ratio = (width / height) if height else 1.0
    lang = max(width, height) / EMU_JE_ZOLL * ZIEL_DPI
    lang = min(LANGE_SEITE_MAX, max(LANGE_SEITE_MIN, lang))
    if ratio >= 1:
        w, h = lang, lang / ratio
    else:
        w, h = lang * ratio, lang

    def rund(v: float) -> int:
        return max(_MINDEST, int(round(v / 16)) * 16)

    return f"{rund(w)}x{rund(h)}"


# Quoted words and their translation right behind are what a prompt wants painted as lettering, unchecked for spelling.
_ZITAT = re.compile(r"(?:(?<!\w)'[^'\n]*'(?!\w)|\"[^\"\n]*\"|„[^“”\n]*[“”]|“[^”\n]*”|«[^»\n]*»)(?:\s*\([^()\n]{0,40}\))?")
OHNE_SCHRIFT = "The picture shows no writing of any kind, only shapes, people and objects."


def ohne_zitate(beschreibung: str) -> str:
    text = re.sub(r"\s+([,.;:])", r"\1", re.sub(r"\s{2,}", " ", _ZITAT.sub("", beschreibung)))
    return re.sub(r"([,.;:])(?:\s*[,;:])+", r"\1", text).strip()


def prompt_fuer(style_text: str, beschreibung: str) -> str:
    return f"{style_text.strip()} Subject: {ohne_zitate(beschreibung)} {OHNE_SCHRIFT}".strip()


def erzeuge(prompt: str, size: str, *, timeout: float = 300.0) -> bytes:
    """One picture as PNG bytes, the square size as a fallback when the provider refuses ours."""
    base_url, model, client = _image_http_client("image_gen", timeout=timeout)
    if not model:
        raise RuntimeError("image_gen route has no model")
    with client:
        antwort = None
        for groesse in (size, _RUECKFALL):
            # The client's door takes the seat, a full provider raises ProviderFull from here.
            antwort = client.post(f"{base_url}/images/generations", json={
                "model": model, "prompt": prompt, "size": groesse, "n": 1, "response_format": "b64_json",
            })
            if antwort.status_code == 200:
                break
            if antwort.status_code != 400 or groesse == _RUECKFALL:
                raise RuntimeError(f"Bildanbieter: {antwort.status_code} {antwort.text[:200]}")
        daten = (antwort.json() or {}).get("data") or []
        if not daten:
            raise RuntimeError("Keine Bilder generiert")
        eintrag = daten[0]
        if eintrag.get("b64_json"):
            return base64.b64decode(eintrag["b64_json"])
        if eintrag.get("url"):
            return client.get(eintrag["url"]).content
        raise RuntimeError("Antwort ohne Bilddaten")
