# backend/src/features/ai_assistant/routes/_chunk_cite.py
"""Resolve model-emitted CHUNK-ID citations into verified, precise position chips.

The model cites the chunk it actually used — ``[N, #C | keyword]`` — where ``C`` is
the ``id`` attribute of the ``<document index="N" id="C">`` block the claim came
from. The model *sees* that id in the context, so it no longer GUESSES a page (the
structural cause of wrong-page chips). We look the chunk up, VERIFY the claim is
really in it (language-agnostic lexical match), and only then emit the real chip with
the chunk's TRUE page/timestamp + offset anchor. Unknown or unverified chunk ids are
dropped — the uncited-line filler (``fill_uncited_lines``) is the safety net. So this
AUGMENTS the existing grounding, it does not replace it. See the chunk-citation spec."""
from __future__ import annotations

import re

from ._citation_match import Unit, match_query
from ._helpers import _CITE_RESOLVE_RE, _format_timestamp, _strip_html

# A chunk-id citation as the model emits it: the position is `#C`, not a page/timestamp.
# `_CITE_RESOLVE_RE` (page/time form) deliberately does NOT match this, so the legacy
# resolver leaves these chips alone until we convert them here.
_CHUNK_CHIP_RE = re.compile(r"\[\s*Q?(\d+)\s*,\s*#\s*(\d+)\s*(?:[|❘]\s*([^\]]+?))?\s*\]")


def _verify(claim: str, content: str, *, is_media: bool) -> bool:
    """True if the claim's text actually occurs in the named chunk (exact normalized
    substring, or token-containment >= threshold; media is stem-aware). Matching runs
    against the ONE named chunk, so no cross-page tie/uniqueness logic applies — this
    is a pure 'is this claim in THIS chunk?' check."""
    if not claim.strip() or not content.strip():
        return False
    unit = Unit(page=None, start_time=None, end_time=None, raw_text=content)
    return match_query(claim, [unit], stem_match=is_media).unit is not None


def _media_timestamp(claim: str, entry: dict, loader) -> float:
    """Precise timestamp = the best transcript segment INSIDE the chunk's time window
    ``[start_time, end_time]``; falls back to the chunk's own start_time when no finer
    segment matches the claim. Keeps the seek landing on the actual moment, not just
    the chunk start."""
    start, end = entry.get("start_time"), entry.get("end_time")
    units_fn = getattr(loader, "units", None)
    if units_fn and start is not None and end is not None:
        try:
            segs = [u for u in units_fn(entry["source"], is_media=True)
                    if u.start_time is not None and start <= u.start_time <= end]
        except Exception:
            segs = []
        if segs:
            r = match_query(claim, segs, stem_match=True)
            if r.unit and r.unit.start_time is not None:
                return r.unit.start_time
    return start if start is not None else 0.0


def resolve_chunk_refs(text: str, registry: dict, loader) -> "tuple[bool, str]":
    """Rewrite every ``[N, #C | kw]`` chunk-id citation into a verified position chip.

    registry: ``{chunk_id: {"qnum": int, "source": row, "is_media": bool,
              "page": int|None, "start_time": float|None, "end_time": float|None,
              "content": str}}``
    loader:   object exposing ``offset_suffixes(source, page, claim)`` and
              ``units(source, is_media=...)`` (the same SourceUnitLoader used elsewhere).

    Returns ``(had_chunk_ref, new_text)``. ``had_chunk_ref`` lets the caller skip the
    legacy page-based resolver for lines already handled here. A verified PDF chip
    carries the chunk's REAL page + offset anchor (Architecture B); media carries the
    precise in-window timestamp. The source number comes from the CHUNK (``entry.qnum``),
    not from the typed ``N`` — the chunk identifies its source uniquely. Unknown or
    unverified ids are dropped and no raw ``#C`` marker ever survives."""
    _offset_suffixes = getattr(loader, "offset_suffixes", None)
    had = False

    def _line(line: str) -> str:
        nonlocal had
        if not _CHUNK_CHIP_RE.search(line):
            return line
        had = True
        # The claim = the line's prose with ALL chips removed (chunk-id chips and any
        # already-resolved chips), so verification/anchoring run on real content, not
        # on the keyword the model copied into the chip.
        claim = _CHUNK_CHIP_RE.sub("", _CITE_RESOLVE_RE.sub("", line)).strip()

        def _sub(m: "re.Match") -> str:
            cid = int(m.group(2))
            kw = _strip_html((m.group(3) or "").strip().strip("\"'").strip())
            entry = registry.get(cid)
            if entry is None:
                return ""  # unknown chunk -> drop
            # Verify + anchor on the chunk's OWN keyword (the model's per-chunk claim,
            # required verbatim by the prompt), not the whole line — a single line may
            # legitimately draw from several chunks, each covering only its part. Fall
            # back to the full claim only when the model omitted the keyword.
            anchor = kw or claim
            if not _verify(anchor, entry.get("content", ""), is_media=entry["is_media"]):
                return ""  # this text is not in the named chunk -> drop (never trust blindly)
            qn = entry["qnum"]
            kw_suffix = f" | {kw}" if kw else ""
            if entry["is_media"]:
                ts = _media_timestamp(anchor, entry, loader)
                return f"[{qn}, {_format_timestamp(ts)}{kw_suffix}]"
            page = entry.get("page")
            if page is None:
                return ""
            if _offset_suffixes is not None:
                try:
                    sufs = _offset_suffixes(entry["source"], page, anchor)
                except Exception:
                    sufs = None
                if sufs:
                    return " ".join(f"[{qn}, S. {page}{s}]" for s in sufs)
            return f"[{qn}, S. {page}{kw_suffix}]"

        out = _CHUNK_CHIP_RE.sub(_sub, line)
        # Tidy spacing left behind by dropped chips.
        out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)
        out = re.sub(r"[ \t]{2,}", " ", out)
        return out.rstrip() if out.strip() else out

    # Materialise BEFORE reading `had`: the generator below sets `had` as a side
    # effect, so the join must run first (a `return had, "\n".join(...)` tuple would
    # capture `had` while still False).
    new = "\n".join(_line(line) for line in text.split("\n"))
    return had, new
