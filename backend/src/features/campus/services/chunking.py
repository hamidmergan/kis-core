"""Splits page markdown into chunks that each carry their heading chain."""
import re

from src.services.text_pieces import PIECE_CHARS, PIECE_OVERLAP, split_spans

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _sections(markdown: str) -> list[tuple[str, str]]:
    """(heading chain, body) per heading, the text before the first heading has an empty chain."""
    chain: list[tuple[int, str]] = []
    out: list[tuple[str, str]] = []
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            out.append((" > ".join(h for _, h in chain), body))
        buf.clear()

    for line in markdown.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level, text = len(m.group(1)), m.group(2).strip()
            chain = [(lv, h) for lv, h in chain if lv < level] + [(level, text)]
        else:
            buf.append(line)
    flush()
    return out


def split_markdown(markdown: str, piece_chars: int = PIECE_CHARS, overlap: int = PIECE_OVERLAP) -> list[dict]:
    """Chunks as dicts with position, heading and content, short sections folded together."""
    merged: list[tuple[str, str]] = []
    for heading, body in _sections(markdown):
        if merged and len(merged[-1][1]) + len(body) < piece_chars:
            prev_heading, prev_body = merged[-1]
            joined = prev_body + ("\n\n" + (f"{heading}\n" if heading and heading != prev_heading else "") + body)
            merged[-1] = (prev_heading, joined)
        else:
            merged.append((heading, body))
    chunks: list[dict] = []
    for heading, body in merged:
        for a, b in split_spans(body, piece_chars, overlap):
            piece = body[a:b].strip()
            if not piece:
                continue
            content = f"{heading}\n{piece}" if heading else piece
            chunks.append({"position": len(chunks), "heading": heading or None, "content": content})
    return chunks
