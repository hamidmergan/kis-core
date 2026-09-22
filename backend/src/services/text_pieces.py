"""Text into pieces of a fixed size, and the cleaning every piece goes through.

Nothing here knows about documents, tools or the assistant. It takes text and
returns text, which is why it sits in services and not in a feature.
"""

import re
import unicodedata

# Chunk size and overlap, all supported models can take this.
PIECE_CHARS = 1000
PIECE_OVERLAP = 200


# Puts standalone accents from LaTeX PDFs back on their letter.
_ACCENT_SCAN_RANGE = range(0x00A0, 0x0300)

# The acute stays out, it is typed as an apostrophe.
_ACCENT_EXCLUDED = {"´"}

# Circumflex and caron added by hand, Unicode knows no decomposition for them.
_ACCENT_EXTRA = {
    "ˆ": "̂",  # MODIFIER LETTER CIRCUMFLEX ACCENT -> COMBINING CIRCUMFLEX
    "ˇ": "̌",  # CARON -> COMBINING CARON
}


def _spacing_accent_marks() -> dict[str, str]:
    """Standalone accent to combining accent, derived from the Unicode data."""
    marks: dict[str, str] = {}
    for code_point in _ACCENT_SCAN_RANGE:
        char = chr(code_point)
        if char in _ACCENT_EXCLUDED:
            continue
        parts = unicodedata.decomposition(char).split()
        if len(parts) == 3 and parts[0] == "<compat>" and parts[1] == "0020":
            marks[char] = chr(int(parts[2], 16))
    return marks | _ACCENT_EXTRA


_SPACING_ACCENTS = _spacing_accent_marks()
_SPACING_ACCENT_RE = re.compile(f"[{re.escape(''.join(_SPACING_ACCENTS))}]")


def _attach_spacing_accents(text: str) -> str:
    """Attach every standalone accent to the letter it belongs to."""
    out: list[str] = []
    index = 0
    end = len(text)
    while index < end:
        char = text[index]
        mark = _SPACING_ACCENTS.get(char)
        if mark:
            # The following letter takes precedence.
            if index + 1 < end and text[index + 1].isalpha():
                out.append(text[index + 1] + mark)
                index += 2
                continue
            # Otherwise the preceding one, as in "A¯" or "p(A¯)".
            if out and out[-1][-1:].isalpha():
                out[-1] += mark
                index += 1
                continue
            # No letter next to it means it cannot be assigned, then it stays.
        out.append(char)
        index += 1
    return "".join(out)


def clean(text: str) -> str:
    """Removes null bytes and reassembles separated accents."""
    if not text:
        return text
    text = text.replace("\x00", "")
    if _SPACING_ACCENT_RE.search(text):
        text = _attach_spacing_accents(text)
    return unicodedata.normalize("NFC", text)


def _merge_small_fragments(chunks: list[str], min_chars: int) -> list[str]:
    """Folds overly short fragments into the neighbour, they would be magnets."""
    if len(chunks) <= 1:
        return chunks
    merged: list[str] = []
    for c in chunks:
        if merged and len(c) < min_chars:
            merged[-1] = (merged[-1] + " " + c).strip()
        else:
            merged.append(c)
    # A tiny leading fragment had no predecessor above; fold it forward instead.
    if len(merged) > 1 and len(merged[0]) < min_chars:
        merged[1] = (merged[0] + " " + merged[1]).strip()
        merged.pop(0)
    return merged


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks of chunk_size chars, breaking at whitespace."""
    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        # Break at last whitespace to avoid cutting words
        if end < len(text):
            last_space = chunk.rfind(" ")
            if last_space > chunk_size // 2:
                chunk = chunk[:last_space]
        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        next_start = start + len(chunk) - overlap
        if next_start <= start:
            break
        # The start is pulled to a word boundary too, otherwise every chunk begins mid-word.
        if not text[next_start - 1].isspace():
            wortanfang = text.rfind(" ", start, next_start)
            if wortanfang + 1 > start:
                next_start = wortanfang + 1
            else:
                # Forward only to the end of the chunk just built, otherwise a word is lost.
                vor = text.find(" ", next_start)
                if vor != -1 and vor + 1 <= start + len(chunk):
                    next_start = vor + 1
        start = next_start
    # Fold tiny remainders in so no header magnets end up in the index.
    return _merge_small_fragments(chunks, max(1, chunk_size // 10))
