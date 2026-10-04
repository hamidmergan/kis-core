"""Main text of a web page as markdown, menus and footers left out."""
import hashlib
import re
from dataclasses import dataclass

import trafilatura
from lxml import html as lxml_html

from src.services.text_pieces import clean

_MIN_WORDS = 20
_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


_CONSENT_XPATH = (
    "//*[@aria-label='cookie-consent' or @id='CookieBox' "
    "or contains(concat(' ', normalize-space(@class), ' '), ' cookie-management ')]"
)


def _without_consent_banner(text: str) -> str:
    """Drops the cookie banner, which trafilatura otherwise picks as the main text of pages without a main element."""
    try:
        tree = lxml_html.fromstring(text)
    except Exception:
        return text
    found = tree.xpath(_CONSENT_XPATH)
    if not found:
        return text
    for el in found:
        if el.getparent() is not None:
            el.getparent().remove(el)
    return lxml_html.tostring(tree, encoding="unicode")


@dataclass(frozen=True)
class Extracted:
    title: str
    markdown: str


def extract_markdown(html: bytes | str, url: str) -> Extracted | None:
    """None when the page carries no readable main text."""
    text = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else html
    text = _without_consent_banner(text)
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


# Raised whenever extraction or chunking changes, pages with an older mark are read again in full.
INDEX_VERSION = 3
HASH_PREFIX = f"v{INDEX_VERSION}:"


def content_hash(markdown: str) -> str:
    return HASH_PREFIX + hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def is_current(digest: str | None) -> bool:
    return bool(digest) and digest.startswith(HASH_PREFIX)
