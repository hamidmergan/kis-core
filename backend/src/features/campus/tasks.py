"""Celery tasks of the campus assistant: the nightly crawl, document indexing and chat cleanup."""
from datetime import datetime, timezone

from loguru import logger

from src.celery_app import celery_app
from src.features.campus.repository import chats as chat_repo
from src.features.campus.repository import pages as page_repo
from src.features.campus.services import crawler, places_sync
from src.features.campus.services import fetch as fetch_mod
from src.features.campus.services import settings as campus_settings
from src.features.campus.services.indexer import embedder, index_markdown
from src.limits import CAMPUS_CRAWL_TIME_LIMIT_SECONDS


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@celery_app.task(
    name="campus.crawl", queue="long",
    soft_time_limit=CAMPUS_CRAWL_TIME_LIMIT_SECONDS, time_limit=CAMPUS_CRAWL_TIME_LIMIT_SECONDS + 300,
)
def run_crawl() -> dict:
    """Syncs the place list and crawls the sitemap, both only when configured."""
    cfg = campus_settings.read()
    if not cfg.sitemap_url and not cfg.places_url:
        return {"skipped": "not configured"}
    status = {"started_at": _now_iso(), "running": True}
    campus_settings.set_crawl_status(status)
    try:
        embed = embedder()
        client = fetch_mod.make_client()
        if cfg.places_url:
            result = fetch_mod.fetch_conditional(client, cfg.places_url)
            if result.status == "ok":
                status["places"] = places_sync.sync(result.body, cfg.map_url, embed)
            else:
                status["places_error"] = result.error or result.status
        else:
            from src import storage
            if storage.key_file_exists("campus/places.json"):
                status["places"] = places_sync.sync(storage.get_key_file("campus/places.json"), cfg.map_url, embed)
        if cfg.sitemap_url:
            status.update(crawler.run(cfg, embed, client=client))
        status["error"] = None
    except Exception as e:
        logger.exception("Campus: Abgleich fehlgeschlagen")
        status["error"] = f"{type(e).__name__}: {e}"[:300]
    status["running"] = False
    status["finished_at"] = _now_iso()
    campus_settings.set_crawl_status(status)
    return status


@celery_app.task(name="campus.sync_places_file", queue="long")
def run_sync_places_file() -> int:
    """Indexes the uploaded places.json, the same way the nightly run does with a place url."""
    from src import storage

    try:
        raw = storage.get_key_file("campus/places.json")
        n = places_sync.sync(raw, campus_settings.read().map_url, embedder())
        status = campus_settings.crawl_status()
        status["places"] = n
        campus_settings.set_crawl_status(status)
        return n
    except Exception as e:
        logger.exception("Campus: Ortsliste nicht indexiert")
        status = campus_settings.crawl_status()
        status["places_error"] = f"{type(e).__name__}: {e}"[:300]
        campus_settings.set_crawl_status(status)
        return 0


@celery_app.task(name="campus.index_document", queue="long")
def run_index_document(page_id: int) -> int:
    """Extracts an uploaded document the way the assistant does and indexes its text."""
    from src.services.aia_chunker import extract_chunks
    from src.storage import open_input_file

    page = page_repo.get_page(page_id)
    if page is None or not page.get("file_path"):
        return 0
    page_repo.set_page_status(page_id, "indexing")
    try:
        file_type = (page.get("filename") or "").rsplit(".", 1)[-1].lower()
        with open_input_file(page["file_path"]) as local_path:
            pieces = extract_chunks(local_path, file_type)
        markdown = f"# {page.get('title') or page.get('filename')}\n\n" + "\n\n".join(
            f"## Seite {p['page_number']}\n\n{p['content']}" if p.get("page_number") else p["content"] for p in pieces
        )
        return index_markdown(page_id, page.get("title"), markdown, embedder(), force=True)
    except Exception as e:
        logger.exception("Campus: Dokument {} nicht indexiert", page_id)
        page_repo.set_page_status(page_id, "failed", f"{type(e).__name__}: {e}")
        return 0


@celery_app.task(name="cleanup.campus_chats", queue="general")
def run_cleanup_campus_chats() -> int:
    """Removes chats nobody touched for the configured number of days. Nightly."""
    try:
        n = chat_repo.prune_chats(campus_settings.read().retention_days)
        if n:
            logger.info("Cleanup: {} Campus-Chat(s) geloescht", n)
        return n
    except Exception as e:
        logger.warning("Cleanup Campus-Chats fehlgeschlagen: {}", e)
        return 0
