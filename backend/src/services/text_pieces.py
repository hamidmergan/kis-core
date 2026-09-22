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


def _merge_small_spans(spans: list[tuple[int, int]], min_chars: int) -> list[tuple[int, int]]:
    """Folds overly short pieces into the neighbour, they would be magnets."""
    if len(spans) <= 1:
        return spans
    merged: list[tuple[int, int]] = []
    for a, b in spans:
        if merged and b - a < min_chars:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    # A tiny leading piece had no predecessor above, fold it forward instead.
    if len(merged) > 1 and merged[0][1] - merged[0][0] < min_chars:
        merged[1] = (merged[0][0], merged[1][1])
        merged.pop(0)
    return merged


def split_spans(text: str, piece_chars: int, overlap: int) -> list[tuple[int, int]]:
    """Where each piece sits in ``text``, as half open ranges, breaking at whitespace.

    The text is taken as it is. Whoever wants the pieces as strings takes the slices,
    whoever wants to point back into the document keeps the numbers.
    """
    if len(text) <= piece_chars:
        return [(0, len(text))] if text.strip() else []
    spans: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        ende = min(start + piece_chars, len(text))
        stueck = text[start:ende]
        # Break at the last whitespace to avoid cutting a word.
        if ende < len(text):
            letzte_luecke = stueck.rfind(" ")
            if letzte_luecke > piece_chars // 2:
                stueck = stueck[:letzte_luecke]
                ende = start + letzte_luecke
        # Stripping moves the boundaries inward, it never drops the piece.
        links = len(stueck) - len(stueck.lstrip())
        rechts = len(stueck) - len(stueck.rstrip())
        a, b = start + links, ende - rechts
        if b > a:
            spans.append((a, b))
        naechster = start + (b - a) - overlap
        if naechster <= start:
            break
        # The start is pulled to a word boundary too, otherwise every piece begins mid-word.
        if not text[naechster - 1].isspace():
            wortanfang = text.rfind(" ", start, naechster)
            if wortanfang + 1 > start:
                naechster = wortanfang + 1
            else:
                # Forward only to the end of the piece just built, otherwise a word is lost.
                vor = text.find(" ", naechster)
                if vor != -1 and vor + 1 <= start + (b - a):
                    naechster = vor + 1
        start = naechster
    # Fold tiny remainders in so no header magnets end up on their own.
    return _merge_small_spans(spans, max(1, piece_chars // 10))


def split_text(text: str, piece_chars: int, overlap: int) -> list[str]:
    """The pieces of a text as strings, the same cut that split_spans makes."""
    text = text.strip()
    return [text[a:b] for a, b in split_spans(text, piece_chars, overlap)]
