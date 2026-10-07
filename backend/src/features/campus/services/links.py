"""Walks the links below start addresses, for site sections that no sitemap lists."""
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlsplit, urlunsplit

from loguru import logger
from lxml import html as lxml_html

from src.features.campus.services import fetch as fetch_mod
from src.features.campus.services import sitemap
from src.features.campus.services.extract import extract_markdown
from src.limits import CAMPUS_CRAWL_CONCURRENCY, CAMPUS_LINK_WALK_MAX_PAGES

# Links to files are no web pages, documents come in through the upload.
_FILE_SUFFIX = re.compile(r"\.(pdf|docx?|pptx?|xlsx?|zip|jpe?g|png|gif|svg|webp|mp4|mp3|ics|vcf)$", re.IGNORECASE)


def _clean(url: str) -> str | None:
    """The address without fragment, None for links with a query since those are views of other pages."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or parts.query:
        return None
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/", "", ""))


def _read(body: bytes, url: str) -> tuple[list[str], bool]:
    """Links of the page and whether it is its own page rather than a view of another address."""
    # Robots tags are ignored on purpose, the site marks real project pages noindex for search engines.
    try:
        tree = lxml_html.fromstring(body)
    except (ValueError, lxml_html.etree.ParserError):
        return [], False
    canonical = [_clean(urljoin(url, c)) for c in tree.xpath("//link[@rel='canonical']/@href")]
    links = [_clean(urljoin(url, h)) for h in tree.xpath("//a/@href")]
    return [link for link in links if link], not canonical or canonical[0] == url


def _text_hash(body: bytes, url: str) -> str | None:
    extracted = extract_markdown(body, url)
    return hashlib.sha256(extracted.markdown.encode()).hexdigest() if extracted else None


def walk(client, start_urls: str, include: list[str], exclude: list[str], fetch_fn=fetch_mod.fetch_conditional, max_pages: int = CAMPUS_LINK_WALK_MAX_PAGES) -> tuple[list[sitemap.SitemapEntry], set[str], bool]:
    """Pages below each start address (one per line) reached by links, the ones not readable tonight, and whether the walk ended before the page cap."""
    starts = [u for u in (_clean(s) for s in sitemap.parse_patterns(start_urls)) if u]
    prefixes = tuple(starts)
    seen: set[str] = set(starts)
    level = list(starts)
    found: list[sitemap.SitemapEntry] = []
    unread: set[str] = set()
    texts: set[str] = set()
    complete = True
    read = 0

    def visit(url: str):
        return url, fetch_fn(client, url)

    with ThreadPoolExecutor(max_workers=max(1, CAMPUS_CRAWL_CONCURRENCY)) as pool:
        while level:
            if read + len(level) > max_pages:
                logger.warning("Campus: Linkgang nach {} Seiten abgebrochen", max_pages)
                level = level[: max_pages - read]
                complete = False
            read += len(level)
            following: list[str] = []
            for url, result in pool.map(visit, level):
                if result.status == "gone":
                    continue
                if result.status != "ok":
                    logger.warning("Campus: Linkgang {} nicht lesbar ({})", url, result.error or result.status)
                    unread.add(url)
                    continue
                links, indexable = _read(result.body, url)
                # The same text under a second address is a copy, the first address found keeps it.
                if indexable and sitemap.allowed(url, include, exclude):
                    digest = _text_hash(result.body, url)
                    if digest and digest not in texts:
                        texts.add(digest)
                        found.append(sitemap.SitemapEntry(url, None))
                for link in links:
                    if link not in seen and link.startswith(prefixes) and not _FILE_SUFFIX.search(link) and fetch_mod.is_web_url(link):
                        seen.add(link)
                        following.append(link)
            level = following if complete else []
    return found, unread, complete
