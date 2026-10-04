"""One nightly pass over the sitemap: fetch what changed, index it, drop what is gone."""
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from loguru import logger

from src.features.campus.repository import pages as page_repo
from src.features.campus.services import fetch as fetch_mod
from src.features.campus.services import indexer, sitemap
from src.features.campus.services.extract import extract_markdown
from src.features.campus.services.settings import CampusSettings
from src.limits import CAMPUS_CRAWL_CONCURRENCY, CAMPUS_CRAWL_MAX_PAGES

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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_lastmod(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def collect_entries(client, sitemap_url: str, include: list[str], exclude: list[str], fetch_fn=fetch_mod.fetch_conditional) -> list[sitemap.SitemapEntry]:
    """Follows index files and returns the allowed page entries, each url once."""
    queue = [sitemap_url]
    done: set[str] = set()
    entries: dict[str, sitemap.SitemapEntry] = {}
    while queue and len(done) < _MAX_SITEMAPS:
        url = queue.pop(0)
        if url in done:
            continue
        done.add(url)
        result = fetch_fn(client, url)
        if result.status != "ok":
            logger.warning("Campus: Sitemap {} nicht lesbar ({})", url, result.error or result.status)
            continue
        children, found = sitemap.parse(result.body)
        queue.extend(c for c in children if c not in done)
        for e in found:
            if e.url not in entries and sitemap.allowed(e.url, include, exclude):
                entries[e.url] = e
    return list(entries.values())


def _process(client, entry: sitemap.SitemapEntry, embed, now: datetime, stats: CrawlStats, lock: threading.Lock, fetch_fn) -> None:
    page = page_repo.get_page_by_url(entry.url)
    if page is None:
        page_id = page_repo.upsert_page(page_repo.KIND_PAGE, entry.url)
        page = {"id": page_id, "etag": None, "last_modified": None, "fetched_at": None, "status": "pending"}
    lastmod = _parse_lastmod(entry.lastmod)
    if page.get("status") == "ready" and page.get("fetched_at") and lastmod and lastmod <= page["fetched_at"]:
        with lock:
            stats.skipped += 1
        return
    result = fetch_fn(client, entry.url, page.get("etag"), page.get("last_modified"))
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
        written = indexer.index_markdown(page["id"], extracted.title, extracted.markdown, embed)
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
) -> dict:
    """Crawls the sitemap of the settings and returns the counts of this run."""
    now = now or _utcnow()
    stats = CrawlStats()
    client = client or fetch_mod.make_client()
    include = sitemap.parse_patterns(settings.url_include)
    exclude = sitemap.parse_patterns(settings.url_exclude)
    entries = collect_entries(client, settings.sitemap_url, include, exclude, fetch_fn)
    stats.seen = len(entries)
    entries = entries[:max_pages]
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        list(pool.map(lambda e: _process(client, e, embed, now, stats, lock, fetch_fn), entries))
    wanted = {e.url for e in entries}
    # Pages beyond the cap were never visited this run and must not be mistaken for gone.
    if stats.seen <= max_pages:
        for url, page_id in page_repo.list_page_urls(page_repo.KIND_PAGE).items():
            if url not in wanted:
                page_repo.delete_page(page_id)
                stats.removed += 1
    return asdict(stats)
