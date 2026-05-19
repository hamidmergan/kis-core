"""KI-Assistent Celery tasks - reindex all sources."""

import concurrent.futures
import os
import re

from langfuse.decorators import langfuse_context, observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import open_input_file
from src.limits import (
    AIA_SUMMARY_MAX_RETRIES,
    AIA_SUMMARY_TIMEOUT_SMALL,
    AIA_SUMMARY_TIMEOUT_LARGE,
    AIA_SUMMARY_MAX_TOKENS_SMALL,
    AIA_SUMMARY_MAX_TOKENS_LARGE,
    AIA_SUMMARY_MAX_TOKENS_BATCH,
    AIA_SUMMARY_CONTENT_MAX_CHARS,
    AIA_SUMMARY_PARALLEL_WORKERS_SMALL,
    AIA_SUMMARY_PARALLEL_WORKERS_LARGE,
    AIA_SUMMARY_BATCH_SIZE,
)
from src.tool_prompts import (
    AIA_SUMMARY_PAGE_SYSTEM as _SUMMARY_SYSTEM,
    AIA_SUMMARY_PAGE_USER_SMALL as _SUMMARY_USER_SMALL,
    AIA_SUMMARY_PAGE_USER_LARGE as _SUMMARY_USER_LARGE,
    AIA_SUMMARY_PAGE_BATCH_USER as _SUMMARY_BATCH_USER,
    AIA_MINDMAP_PROMPT,
)

from src.features.ai_assistant.tasks._helpers import (
    _format_ts,
    _save_aia_output,
    _detect_language,
    _parse_numbered_summaries,
    _clean_summary,
    _call_llm_with_retry,
    _summarize_page,
    _summarize_batch,
    _get_llm_client,
    _clean_llm_json,
    generate_doc_summary,
)

@celery_app.task(bind=True, name="aia.reindex_all_sources", queue="aia")
def run_reindex_all_sources(self):
    """Re-embed all existing KI-Assistent chunks with the current embedding provider.

    Triggered by admin after an embedding-model change. Preserves source UUIDs,
    file paths, chunk IDs and page numbers - so chips/notes/tools stay intact.
    Only the embedding vectors are replaced. Paragraph summaries are untouched
    (LLM-generated, not embedding-dependent).
    """
    import json as _json
    from src.services.aia_embeddings import get_embedding_provider, compute_fingerprint

    provider = get_embedding_provider()
    fingerprint = compute_fingerprint(provider)
    embedding_model = provider.model_name

    sources = db.get_all_aia_sources()
    total = len(sources)
    done = 0

    def _set_progress(current: str, failed: int = 0):
        db.set_setting("reindex_progress", _json.dumps({
            "total": total, "done": done, "current": current, "failed": failed,
            "running": True,
        }))

    _set_progress("start")
    logger.info("KI Tutor reindex: starting over {} sources", total)

    workspace_ids_seen: set[int] = set()
    failed = 0

    for source in sources:
        source_uuid = source["uuid"]
        filename = source.get("filename") or ""
        try:
            _set_progress(filename)
            chunks = db.get_aia_chunks_by_source(source["id"])
            if not chunks:
                logger.info("KI Tutor reindex: source {} has no chunks, skipping", source_uuid)
            else:
                _BATCH = 20
                for i in range(0, len(chunks), _BATCH):
                    batch = chunks[i: i + _BATCH]
                    texts = [c["content"] for c in batch]
                    vectors = provider.embed(texts)
                    for c, vec in zip(batch, vectors):
                        db.update_chunk_embedding(c["id"], vec)
                logger.info("KI Tutor reindex: source {} re-embedded ({} chunks)", source_uuid, len(chunks))

            db.update_aia_source_status(source_uuid, "ready", embedding_model=embedding_model)
            workspace_ids_seen.add(source["workspace_id"])
        except Exception as e:
            failed += 1
            logger.error("KI Tutor reindex: source {} failed: {}", source_uuid, e)
            db.update_aia_source_status(source_uuid, "failed", error_message=str(e))
        finally:
            done += 1
            _set_progress(filename, failed=failed)

    # Bump fingerprint on every touched workspace so the new provider is recorded
    for workspace_id in workspace_ids_seen:
        workspace = db.get_aia_workspace_by_id(workspace_id)
        if workspace:
            db.update_aia_workspace_status(
                workspace["uuid"], "ready",
                embedding_model=embedding_model,
                embedding_fingerprint=fingerprint,
            )

    db.set_setting("reindex_progress", _json.dumps({
        "total": total, "done": done, "current": "done", "failed": failed,
        "running": False,
    }))
    logger.info("KI Tutor reindex: finished ({} ok, {} failed)", done - failed, failed)


@celery_app.task(bind=True, name="aia.reindex_workspace", queue="aia")
def run_reindex_workspace(self, workspace_uuid: str):
    """Re-embed every chunk of one workspace with the current embedding provider.

    Used after a workspace import where the bundled embedding model differs from
    the active one — the import permissively loads chunks+vectors, this task
    rewrites them to match the current provider.
    """
    import json as _json
    from src.services.aia_embeddings import get_embedding_provider, compute_fingerprint

    workspace = db.get_aia_workspace(workspace_uuid)
    if workspace is None:
        logger.warning("KI Tutor reindex-workspace: {} not found", workspace_uuid)
        return

    provider = get_embedding_provider()
    fingerprint = compute_fingerprint(provider)
    embedding_model = provider.model_name

    sources = db.get_aia_sources_by_workspace(workspace["id"])
    progress_key = f"reindex_workspace_progress_{workspace_uuid}"
    total = len(sources)
    done = 0
    failed = 0

    def _set_progress(current: str):
        db.set_setting(progress_key, _json.dumps({
            "total": total, "done": done, "current": current, "failed": failed,
            "running": True,
        }))

    _set_progress("start")
    logger.info("KI Tutor reindex-workspace {}: {} sources", workspace_uuid, total)

    for source in sources:
        source_uuid = source["uuid"]
        filename = source.get("filename") or ""
        try:
            _set_progress(filename)
            chunks = db.get_aia_chunks_by_source(source["id"])
            if chunks:
                _BATCH = 20
                for i in range(0, len(chunks), _BATCH):
                    batch = chunks[i: i + _BATCH]
                    vectors = provider.embed([c["content"] for c in batch])
                    for c, vec in zip(batch, vectors):
                        db.update_chunk_embedding(c["id"], vec)
            db.update_aia_source_status(source_uuid, "ready", embedding_model=embedding_model)
        except Exception as e:
            failed += 1
            logger.error("KI Tutor reindex-workspace: source {} failed: {}", source_uuid, e)
            db.update_aia_source_status(source_uuid, "failed", error_message=str(e))
        finally:
            done += 1
            _set_progress(filename)

    db.update_aia_workspace_status(
        workspace_uuid, "ready",
        embedding_model=embedding_model,
        embedding_fingerprint=fingerprint,
    )
    db.set_setting(progress_key, _json.dumps({
        "total": total, "done": done, "current": "done", "failed": failed,
        "running": False,
    }))
    logger.info("KI Tutor reindex-workspace {}: done ({} ok, {} failed)",
                workspace_uuid, done - failed, failed)


@celery_app.task(bind=True, name="aia.backfill_doc_summaries", queue="aia")
def run_backfill_doc_summaries(self, limit: int | None = None):
    """One-shot: generate doc-summaries for every source that doesn't have one yet.

    Triggered manually after rollout (admin endpoint or shell). Soft-failure on
    individual sources - logs and moves on. ``limit`` caps the number of sources
    processed in one run; useful for dry-runs and rate-limit-aware batching.
    """
    sources = db.get_all_aia_sources()
    pending = [s for s in sources if s.get("status") == "ready" and not s.get("summary")]
    if limit is not None:
        pending = pending[:limit]

    total = len(pending)
    logger.info("KI Tutor doc-summary backfill: {} sources pending", total)

    done = 0
    failed = 0
    for s in pending:
        try:
            generate_doc_summary(s["uuid"])
            done += 1
        except Exception as e:
            failed += 1
            logger.warning("KI Tutor doc-summary backfill: {} failed: {}", s["uuid"], e)

    logger.info("KI Tutor doc-summary backfill: done ({} ok, {} failed of {})",
                done, failed, total)
    return {"total": total, "ok": done, "failed": failed}


@celery_app.task(bind=True, name="aia.backfill_page_summaries", queue="aia")
def run_backfill_page_summaries(self):
    """One-shot: generate page-summaries for every PDF source that has none.

    Only PDFs are eligible - media has no page concept. Dispatches the regular
    ``run_generate_summaries`` task per source; that task is resume-safe and
    will chain a fresh doc-summary at the end (so citations get accurate page
    numbers in the multi-source GENERIC chat path).
    """
    from src.features.ai_assistant.tasks.ingestion import run_generate_summaries

    sources = db.get_all_aia_sources()
    pending = []
    for s in sources:
        if s.get("status") != "ready":
            continue
        if s.get("file_type") != "pdf":
            continue
        if db.get_page_summaries_by_source(s["id"]):
            continue
        pending.append(s)

    total = len(pending)
    logger.info("KI Tutor page-summary backfill: {} PDFs pending", total)

    for s in pending:
        run_generate_summaries.delay(s["uuid"])

    return {"total": total, "queued": total}
