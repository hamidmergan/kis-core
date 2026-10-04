"""Reads sitemap files and decides which of their links belong into the index."""
from dataclasses import dataclass
from xml.etree import ElementTree

_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


@dataclass(frozen=True)
class SitemapEntry:
    url: str
    lastmod: str | None


def parse(xml_bytes: bytes) -> tuple[list[str], list[SitemapEntry]]:
    """Child sitemaps of an index file and the page entries of a urlset, either may be empty."""
    # A sitemap never needs a DTD, one with entities is refused before the parser sees it.
    head = xml_bytes[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        return [], []
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return [], []
    children: list[str] = []
    entries: list[SitemapEntry] = []
    for node in root.iter():
        tag = node.tag.replace(_NS, "")
        if tag not in ("sitemap", "url"):
            continue
        loc = node.find(f"{_NS}loc")
        if loc is None or not (loc.text or "").strip():
            loc = node.find("loc")
        if loc is None or not (loc.text or "").strip():
            continue
        lastmod = node.find(f"{_NS}lastmod")
        if lastmod is None:
            lastmod = node.find("lastmod")
        text = loc.text.strip()
        if tag == "sitemap":
            children.append(text)
        else:
            entries.append(SitemapEntry(text, (lastmod.text or "").strip() or None if lastmod is not None else None))
    return children, entries


def parse_patterns(text: str) -> list[str]:
    """One pattern per line, blank lines do not count."""
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def allowed(url: str, include: list[str], exclude: list[str]) -> bool:
    """A link passes when no exclude pattern and, if any are set, at least one include pattern occurs in it."""
    low = url.lower()
    if any(p.lower() in low for p in exclude):
        return False
    if include and not any(p.lower() in low for p in include):
        return False
    return True
