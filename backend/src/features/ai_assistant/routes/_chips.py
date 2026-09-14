"""Builds a source chip and decides which line may carry one."""

import re
from typing import Optional

from src.services.aia_segment_pick import best_index, rare_stems, rarity_weights

from ._media_files import _chunk_segments
from ._text import (
    _DEDUP_MIN_KEY_LEN,
    _TOKEN_RE,
    _format_timestamp,
    _is_table_delim,
    _is_table_row,
    _line_dedup_key,
    _norm_for_match,
    _significant_tokens,
)


# How much of a word start counts when comparing with a transcript segment.
_SEGMENT_STEM_CHARS = 6


# How many word stems a segment must carry to fix the timestamp.
_SEGMENT_MIN_STEM_HITS = 2


# One stem carries the timestamp alone when it occurs rarely enough.
_SEGMENT_RARE_MAX_DF = 3


# For that the source needs enough segments per allowed occurrence.
_SEGMENT_RARE_SEGMENTS_PER_HIT = 25


# Numbers count as a feature of their own, even when short.
_SEGMENT_MIN_NUM_CHARS = 2


_SEGMENT_HYPHEN_RE = re.compile(r"-+")


def _norm_for_segment(s: str) -> str:
    """Like :func:`_norm_for_match`, but the hyphen counts as a space."""
    return re.sub(r"\s+", " ", _SEGMENT_HYPHEN_RE.sub(" ", _norm_for_match(s))).strip()


def _segment_stems(line: str) -> set[str]:
    """Features of an answer line for the segment comparison."""
    line = _SEGMENT_HYPHEN_RE.sub(" ", line)
    stems = {_norm_for_segment(t)[:_SEGMENT_STEM_CHARS] for t in _significant_tokens(line)}
    for w in _TOKEN_RE.findall(re.sub(r"[*_`~#>]+", " ", line)):
        wl = _norm_for_segment(w.strip(".,-:;"))
        if len(wl) >= _SEGMENT_MIN_NUM_CHARS and any(ch.isdigit() for ch in wl):
            stems.add(wl)
    stems.discard("")
    return stems


def _line_segment_start(line: str, chunk: dict, segments: list[dict]) -> Optional[float]:
    """Start time of the segment carrying the cited line, or None."""
    segs = _chunk_segments(chunk, segments)
    if len(segs) < 2:
        return None
    stems = _segment_stems(line)
    if not stems:
        return None
    treffer = [[stem for stem in stems if stem in _norm_for_segment(s.get("text") or "")]
               for s in segs]
    selten = rare_stems(chunk.get("source_id"), segments, _segment_stems, _norm_for_segment,
                        min(_SEGMENT_RARE_MAX_DF,
                            len(segments) // _SEGMENT_RARE_SEGMENTS_PER_HIT))
    if (max((len(t) for t in treffer), default=0) < _SEGMENT_MIN_STEM_HITS
            and not any(selten.intersection(t) for t in treffer)):
        return None
    gewichte = rarity_weights(chunk.get("source_id"), segments,
                              _segment_stems, _norm_for_segment)
    return segs[best_index(treffer, gewichte)]["start"]


def _attribution_chip(qnum: int, chunk: dict, line: str,
                      segments: Optional[list[dict]] = None) -> list[str]:
    """Source chip to jump with: a timestamp for media, a page number for PDF."""
    st = chunk.get("start_time")
    if st is not None:
        if line and segments:
            seg_start = _line_segment_start(line, chunk, segments)
            if seg_start is not None:
                st = seg_start
        return [f"[{qnum}, {_format_timestamp(st)}]"]
    page = chunk.get("page_number")
    return [f"[{qnum}, S. {page}]"] if page is not None else []


def _append_scope_anchor(text: str, qnum: int, page: int) -> str:
    """Appends exactly one page chip at the end of a single-page summary."""
    return f"{text.rstrip()}\n\n[{qnum}, S. {page}]"


def _is_label_line(line: str) -> bool:
    """A line ending in a colon only introduces and gets no chip."""
    s = re.sub(r"[*_`~\s]+$", "", line.rstrip())
    return s.endswith(":")


# A line entirely in bold counts as a heading.
_BOLD_HEADING_RE = re.compile(r"^(\*\*|__)(?:(?!\1).)+\1[\s.?!:]*$")


def _is_heading_line(line: str) -> bool:
    """A heading, as a hash or fully bold, claims nothing and gets no chip."""
    return line.lstrip().startswith("#") or bool(_BOLD_HEADING_RE.match(line.strip()))


def _lead_in_lines(lines: list[str]) -> set:
    """The lines of an overview that lead in to the sections instead of claiming anything.

    An overview opens with a sentence about the material as a whole, and no single spot can
    back that. Measured against a real overview over 30 statutes: every word based rule
    puts a chip there anyway, because the lead-in reuses ordinary words of the material.
    What gives it away is not its words but its place, in front of the first section."""
    heads = [i for i, ln in enumerate(lines) if _is_heading_line(ln)]
    if not heads:
        return set()            # no sections, so no lead-in either
    if not any(lines[i].strip() for i in range(heads[0])):
        heads = heads[1:]       # a title at the very top names the answer, not a section
    return set(range(heads[0])) if heads else set()


# A line already has evidence when it ends with a chip.
_HAS_CITE = re.compile(r"\[(?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)[^\]]*\]\s*\|?\s*$")


def _needs_attribution(line: str) -> bool:
    """Whether a line can carry a chip at all."""
    return (len(_line_dedup_key(line)) >= _DEDUP_MIN_KEY_LEN
            and not _is_table_delim(line)
            and not _is_label_line(line)
            and not _is_heading_line(line)
            and not _HAS_CITE.search(line.rstrip()))


def _attach_chips(text: str, chip_str: str) -> str:
    """Puts the chip before the final period, otherwise simply at the end."""
    s = text.rstrip()
    i = len(s)
    while i > 0 and s[i - 1] in ".!?":
        i -= 1
    if 0 < i < len(s):                     # a real terminal-punctuation run with text before it
        return f"{s[:i].rstrip()} {chip_str}{s[i:]}"
    return f"{s} {chip_str}"


def _place_chip(line: str, chip_str: str) -> str:
    """Appends the chip to a line, in a table row into the last cell."""
    if _is_table_row(line):
        return re.sub(r"\s*\|\s*$", f" {chip_str} |", line.rstrip())
    return _attach_chips(line, chip_str)


def _is_continuation(line: str) -> bool:
    """A line that continues the previous block instead of starting a new one."""
    s = line.strip()
    if not s or _is_table_row(line):
        return False
    ls = line.lstrip()
    if _is_heading_line(line):
        return False
    if re.match(r"[-*+]\s", ls) or re.match(r"\d+[.)]\s", ls):
        return False
    return True


def _attr_blocks(lines: list[str]) -> list[list[int]]:
    """Groups lines into evidence blocks, the chip goes on the last line."""
    blocks: list[list[int]] = []
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].strip():
            i += 1
            continue
        if _is_table_row(lines[i]) or _is_heading_line(lines[i]):
            blocks.append([i])
            i += 1
            continue
        blk = [i]
        i += 1
        while i < n and _is_continuation(lines[i]):
            blk.append(i)
            i += 1
        blocks.append(blk)
    return blocks


def _is_prose_line(line: str) -> bool:
    """An ordinary prose line, no bullet, no heading, no table."""
    ls = line.lstrip()
    if not ls.strip() or _is_table_row(line) or _is_table_delim(line):
        return False
    if _is_heading_line(line):
        return False
    if re.match(r"[-*+]\s", ls) or re.match(r"\d+[.)]\s", ls):
        return False
    return True
