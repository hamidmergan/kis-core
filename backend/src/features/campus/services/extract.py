"""Main text of a web page as markdown, menus and footers left out."""
import hashlib
import re
from dataclasses import dataclass

import trafilatura

from src.services.text_pieces import clean

_MIN_WORDS = 20
_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Extracted:
    title: str
    markdown: str


def extract_markdown(html: bytes | str, url: str) -> Extracted | None:
    """None when the page carries no readable main text."""
    text = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else html
    markdown = trafilatura.extract(
        text, url=url, output_format="markdown", include_links=False, include_tables=True,
        include_comments=False, include_images=False, favor_recall=False,
    ) or ""
    markdown = clean(markdown).strip()
    if len(markdown.split()) < _MIN_WORDS:
        return None
    title = ""
    try:
        meta = trafilatura.extract_metadata(text, default_url=url)
        title = (meta.title or "").strip() if meta else ""
    except Exception:
        title = ""
    if not title:
        m = _HEADING_RE.search(markdown)
        title = m.group(1).strip() if m else url
    return Extracted(title=title[:200], markdown=markdown)


def content_hash(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()
