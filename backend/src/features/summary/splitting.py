"""Cuts a document too long for one call into balanced parts along its own structure."""

import math
import re

from src.limits import SUMMARY_PART_FALLBACK_CHARS, SUMMARY_PART_MIN_CHARS
from src.services.model_limits import cap_for_model

# Tried in this order, each pattern ending exactly where the next part begins.
_BOUNDARIES = (
    re.compile(r"\n+(?=(?:§+|Art\.|Artikel|Anlage|Anhang|Kapitel|Abschnitt)[\s\d])"),
    re.compile(r"\n+(?=#{1,6}\s)"),
    re.compile(r"\n\s*\n"),
    re.compile(r"(?<=[.!?])\s+"),
)

# Half the window for the part, the rest for prompt, plan and answer.
_WINDOW_SHARE = 0.5


def part_size_for_chat() -> int:
    """The largest part the chat model provably takes, the fallback when unmeasured."""
    groesse = cap_for_model(SUMMARY_PART_FALLBACK_CHARS, _WINDOW_SHARE, "chat")
    return max(SUMMARY_PART_MIN_CHARS, groesse)


def _cut_point(text: str, lo: int, hi: int, want: int) -> int | None:
    """The best boundary between lo and hi, the one closest to want."""
    for muster in _BOUNDARIES:
        stellen = [t.end() for t in muster.finditer(text, lo, hi) if lo < t.end() <= hi]
        if stellen:
            return min(stellen, key=lambda s: abs(s - want))
    return None


def split_text(text: str, *, maximum: int, threshold: int | None = None) -> list[str]:
    """The document as one piece, or as balanced parts once it passes the threshold."""
    grenze = threshold if threshold is not None else maximum
    if len(text) <= grenze:
        return [text]
    teile: list[str] = []
    pos = 0
    while pos < len(text):
        rest = len(text) - pos
        if rest <= maximum:
            teile.append(text[pos:])
            break
        # Recomputed every round, a fixed target would leave a stub at the end.
        ziel = math.ceil(rest / math.ceil(rest / maximum))
        lo = pos + max(1, ziel // 2)
        hi = pos + maximum
        schnitt = _cut_point(text, lo, hi, pos + ziel) or hi
        teile.append(text[pos:schnitt])
        pos = schnitt
    return [t for t in teile if t.strip()]


def split_sources(documents: list[dict], *, maximum: int,
                  threshold: int | None = None) -> list[dict]:
    """Every document as one or more units, each still naming the file it came from."""
    einheiten: list[dict] = []
    for dokument in documents:
        stuecke = split_text(dokument["content"], maximum=maximum, threshold=threshold)
        gesamt = len(stuecke)
        for nummer, inhalt in enumerate(stuecke, start=1):
            geteilt = gesamt > 1
            einheiten.append({
                "source_id": f"{dokument['source_id']}t{nummer}" if geteilt
                             else dokument["source_id"],
                "filename": dokument["filename"],
                "content": inhalt,
                "origin": dokument["source_id"],
                "part": nummer,
                "parts": gesamt,
                "label": f"{dokument['filename']} (Teil {nummer} von {gesamt})" if geteilt
                         else dokument["filename"],
            })
    return einheiten


def part_note(units: list[dict], keep: set[str] | None = None) -> str:
    """Which ids are parts of the same file, limited to keep when it is given."""
    gruppen: dict[str, list[str]] = {}
    for einheit in units:
        if einheit.get("parts", 1) < 2:
            continue
        if keep is not None and einheit["source_id"] not in keep:
            continue
        gruppen.setdefault(einheit["filename"], []).append(einheit["source_id"])
    return "\n".join(f"- {name}: {', '.join(ids)}" for name, ids in gruppen.items())


def original_names(units: list[dict]) -> list[str]:
    """The uploaded file names in order, each once however often it was cut."""
    gesehen: set[str] = set()
    namen: list[str] = []
    for einheit in units:
        herkunft = einheit.get("origin") or einheit["source_id"]
        if herkunft in gesehen:
            continue
        gesehen.add(herkunft)
        namen.append(einheit["filename"])
    return namen
