"""Turns a fetched page into the small HTML file LibreOffice renders to PDF."""
from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

import trafilatura

from src.i18n import t
from src.limits import WEB_PAGE_MIN_WORDS, WEB_PAGE_TITLE_MAX_CHARS
from src.services.web_page_fetch import LinkError

_TZ = ZoneInfo("Europe/Berlin")
_BAD_NAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_WS = re.compile(r"\s+")
_TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_BODY_TAG = re.compile(r"<body[^>]*>(.*)</body>", re.IGNORECASE | re.DOTALL)
# Tags that would make LibreOffice reach out, and attributes that carry a target.
_OUTSIDE_TAGS = re.compile(
    r"<(script|style|iframe|object|embed)\b[^>]*>.*?</\1>"
    r"|<(?:img|link|source|video|audio|iframe)\b[^>]*/?>",
    re.IGNORECASE | re.DOTALL,
)
_OUTSIDE_ATTRS = re.compile(
    r"""\s(?:href|src|srcset|poster|background|style)\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""",
    re.IGNORECASE,
)


@dataclass
class PageDocument:
    title: str
    body_html: str
    word_count: int


def extract_html_page(raw: bytes, url: str) -> PageDocument:
    """Main text of an HTML page, navigation and banners dropped."""
    meta = trafilatura.bare_extraction(
        raw, url=url, include_images=False, include_links=False, with_metadata=True,
    )
    text = _field(meta, "text") or ""
    words = len(text.split())
    if words < WEB_PAGE_MIN_WORDS:
        raise LinkError("ai.link.noText", 422)
    body = trafilatura.extract(
        raw, url=url, output_format="html",
        include_images=False, include_links=False, include_tables=True,
    ) or ""
    title = _field(meta, "title") or _title_tag(raw) or title_from_url(url)
    return PageDocument(title=title.strip(), body_html=strip_outside(_inner_body(body)), word_count=words)


def extract_text_page(raw: bytes, url: str) -> PageDocument:
    """A plain text answer becomes paragraphs, blank lines split them."""
    text = raw.decode("utf-8", errors="replace")
    words = len(text.split())
    if words < WEB_PAGE_MIN_WORDS:
        raise LinkError("ai.link.noText", 422)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    body = "".join(f"<p>{_html.escape(p)}</p>" for p in paragraphs)
    return PageDocument(title=title_from_url(url), body_html=body, word_count=words)


def build_document_html(title: str, url: str, body_html: str, fetched_at: datetime, locale: str) -> str:
    """The file LibreOffice renders, without a single reference to the outside."""
    date_format = "%Y-%m-%d" if locale == "en" else "%d.%m.%Y"
    stamp = fetched_at.astimezone(_TZ).strftime(date_format)
    line = t("ai.link.sourceLine", locale, url=url, date=stamp)
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<title>{_html.escape(title)}</title></head><body>"
        f"<h1>{_html.escape(title)}</h1><p>{_html.escape(line)}</p>"
        f"{body_html}</body></html>"
    )


def safe_filename(title: str) -> str:
    """A title as a file name: forbidden characters out, whitespace squeezed, length capped."""
    clean = _WS.sub(" ", _BAD_NAME_CHARS.sub(" ", title)).strip()
    clean = clean[:WEB_PAGE_TITLE_MAX_CHARS].strip().rstrip(".").strip()
    return clean or "seite"


def title_from_url(url: str) -> str:
    """Host plus path when the page names no title."""
    parts = urlsplit(url)
    path = unquote(parts.path).rstrip("/")
    return f"{parts.hostname or ''}{path}" or "seite"


def pdf_title_from_url(url: str) -> str:
    """Last path segment without its extension, otherwise the host."""
    parts = urlsplit(url)
    name = PurePosixPath(unquote(parts.path)).stem
    return name or (parts.hostname or "seite")


def strip_outside(fragment: str) -> str:
    """Removes every tag and attribute that could point somewhere else."""
    fragment = _OUTSIDE_TAGS.sub("", fragment)
    return _OUTSIDE_ATTRS.sub("", fragment)


def _field(doc: object, name: str) -> str | None:
    """trafilatura hands back an object or a dict, depending on the version."""
    if doc is None:
        return None
    if isinstance(doc, dict):
        return doc.get(name)
    return getattr(doc, name, None)


def _inner_body(document: str) -> str:
    m = _BODY_TAG.search(document)
    return m.group(1) if m else document


def _title_tag(raw: bytes) -> str | None:
    m = _TITLE_TAG.search(raw.decode("utf-8", errors="replace"))
    if not m:
        return None
    title = _WS.sub(" ", _html.unescape(m.group(1))).strip()
    return title or None
