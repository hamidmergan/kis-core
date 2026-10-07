"""One nightly pass over the sitemap: fetch what changed, index it, drop what is gone."""
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from loguru import logger

from src.features.campus.repository import pages as page_repo
from src.features.campus.services import fetch as fetch_mod
from src.features.campus.services import indexer, links, sitemap
from src.features.campus.services.extract import extract_markdown, is_current
from src.features.campus.services.settings import CampusSettings
from src.limits import CAMPUS_CRAWL_CONCURRENCY, CAMPUS_CRAWL_MAX_PAGES, CAMPUS_PAGE_MAX_CHUNKS

_MAX_SITEMAPS = 50


@dataclass
class CrawlStats:
    seen: int = 0
    fetched: int = 0
    unchanged: int = 0
    indexed: int = 0
    removed: int = 0
    failed: int = 0
    skipped: int = 0
    capped: int = 0
    max_pages: int = 0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_lastmod(value: str | None) -> datetime | None:
    """A date without time counts as the end of that day, a change later that day must not be skipped."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if "T" not in value and " " not in value.strip():
        dt = dt.replace(hour=23, minute=59, second=59)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def collect_entries(client, sitemap_urls: str, include: list[str], exclude: list[str], fetch_fn=fetch_mod.fetch_conditional) -> tuple[list[sitemap.SitemapEntry], bool]:
    """Follows index files of every start url (one per line) and returns the allowed page entries, each url once, and whether every sitemap was read."""
    queue = sitemap.parse_patterns(sitemap_urls)
    done: set[str] = set()
    entries: dict[str, sitemap.SitemapEntry] = {}
    complete = True
    while queue and len(done) < _MAX_SITEMAPS:
        url = queue.pop(0)
        if url in done:
            continue
        done.add(url)
        result = fetch_fn(client, url)
        if result.status != "ok":
            logger.warning("Campus: Sitemap {} nicht lesbar ({})", url, result.error or result.status)
            complete = False
            continue
        parsed = sitemap.parse(result.body)
        if parsed is None:
            logger.warning("Campus: Sitemap {} ist keine lesbare Sitemap", url)
            complete = False
            continue
        children, found = parsed
        queue.extend(c for c in children if c not in done)
        for e in found:
            if e.url not in entries and sitemap.allowed(e.url, include, exclude):
                entries[e.url] = e
    if queue:
        complete = False
    return list(entries.values()), complete


def _process(client, entry: sitemap.SitemapEntry, embed, now: datetime, stats: CrawlStats, lock: threading.Lock, fetch_fn) -> None:
    """One page; a failure counts for this page only and never stops the run."""
    try:
        _process_one(client, entry, embed, now, stats, lock, fetch_fn)
    except Exception as e:  # noqa: BLE001
        logger.warning("Campus: Seite {} fehlgeschlagen: {}", entry.url, e)
        with lock:
            stats.failed += 1


def _process_one(client, entry: sitemap.SitemapEntry, embed, now: datetime, stats: CrawlStats, lock: threading.Lock, fetch_fn) -> None:
    # A sitemap entry that is no public web link never gets a row.
    if not fetch_mod.is_web_url(entry.url):
        with lock:
            stats.failed += 1
        return
    page = page_repo.get_page_by_url(entry.url)
    if page is None:
        page_id = page_repo.upsert_page(page_repo.KIND_PAGE, entry.url)
        page = {"id": page_id, "etag": None, "last_modified": None, "fetched_at": None, "status": "pending"}
    lastmod = _parse_lastmod(entry.lastmod)
    # A page indexed by an older version is fetched in full, whatever the server says about changes.
    current = page.get("status") == "ready" and is_current(page.get("content_hash"))
    if current and page.get("fetched_at") and lastmod and lastmod <= page["fetched_at"]:
        with lock:
            stats.skipped += 1
        return
    etag, last_modified = (page.get("etag"), page.get("last_modified")) if current else (None, None)
    result = fetch_fn(client, entry.url, etag, last_modified)
    if result.status == "unchanged":
        page_repo.set_page_fetch(page["id"], page.get("etag"), page.get("last_modified"), now)
        with lock:
            stats.unchanged += 1
        return
    if result.status == "gone":
        page_repo.delete_page(page["id"])
        with lock:
            stats.removed += 1
        return
    if result.status != "ok":
        page_repo.set_page_status(page["id"], "failed", result.error)
        with lock:
            stats.failed += 1
        return
    with lock:
        stats.fetched += 1
    page_repo.set_page_fetch(page["id"], result.etag, result.last_modified, now)
    extracted = extract_markdown(result.body, entry.url)
    if extracted is None:
        page_repo.set_page_status(page["id"], "failed", "no text")
        with lock:
            stats.failed += 1
        return
    try:
        written = indexer.index_markdown(page["id"], extracted.title, extracted.markdown, embed, max_chunks=CAMPUS_PAGE_MAX_CHUNKS)
    except Exception as e:
        page_repo.set_page_status(page["id"], "failed", f"index: {e}"[:200])
        with lock:
            stats.failed += 1
        return
    with lock:
        if written:
            stats.indexed += 1
        else:
            stats.unchanged += 1


def run(
    settings: CampusSettings,
    embed,
    client=None,
    now: datetime | None = None,
    max_pages: int = CAMPUS_CRAWL_MAX_PAGES,
    concurrency: int = CAMPUS_CRAWL_CONCURRENCY,
    fetch_fn=fetch_mod.fetch_conditional,
    excluded_urls: set[str] | None = None,
) -> dict:
    """Crawls the sitemaps and the link walks of the settings and returns the counts of this run."""
    now = now or _utcnow()
    stats = CrawlStats(max_pages=max_pages)
    client = client or fetch_mod.make_client()
    include = sitemap.parse_patterns(settings.url_include)
    exclude = sitemap.parse_patterns(settings.url_exclude)
    entries, complete = collect_entries(client, settings.sitemap_url, include, exclude, fetch_fn)
    walked, unread, walk_complete = links.walk(client, settings.start_urls, include, exclude, fetch_fn)
    known_entries = {e.url for e in entries}
    entries += [e for e in walked if e.url not in known_entries]
    complete = complete and walk_complete
    if excluded_urls:
        entries = [e for e in entries if e.url not in excluded_urls]
    stats.seen = len(entries)
    # A walked page that failed tonight is not refetched but also not counted as gone.
    listed = {e.url for e in entries} | unread
    # Only a full, non-empty read of the sitemap may count missing pages as gone.
    if complete and entries:
        for url, page_id in page_repo.list_page_urls(page_repo.KIND_PAGE).items():
            if url not in listed:
                page_repo.delete_page(page_id)
                stats.removed += 1
    # Known pages stay current, new links only fill the room left under the cap.
    known = set(page_repo.list_page_urls(page_repo.KIND_PAGE))
    new = [e for e in entries if e.url not in known]
    room = max(0, max_pages - len(known))
    stats.capped = max(0, len(new) - room)
    entries = [e for e in entries if e.url in known] + new[:room]
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        list(pool.map(lambda e: _process(client, e, embed, now, stats, lock, fetch_fn), entries))
    if stats.capped:
        logger.warning("Campus: Obergrenze von {} Seiten erreicht, {} neue Seiten nicht aufgenommen", max_pages, stats.capped)
    return asdict(stats)
