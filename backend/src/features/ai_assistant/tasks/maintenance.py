"""KI-Assistent Celery tasks — reindex all sources."""

import concurrent.futures
import os
import re

from langfuse.decorators import langfuse_context, observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import open_input_file
from src.limits import (
    KIA_SUMMARY_MAX_RETRIES,
    KIA_SUMMARY_TIMEOUT_SMALL,
    KIA_SUMMARY_TIMEOUT_LARGE,
    KIA_SUMMARY_MAX_TOKENS_SMALL,
    KIA_SUMMARY_MAX_TOKENS_LARGE,
    KIA_SUMMARY_MAX_TOKENS_BATCH,
    KIA_SUMMARY_CONTENT_MAX_CHARS,
    KIA_SUMMARY_PARALLEL_WORKERS_SMALL,
    KIA_SUMMARY_PARALLEL_WORKERS_LARGE,
    KIA_SUMMARY_BATCH_SIZE,
)
from src.tool_prompts import (
    KIA_SUMMARY_PAGE_SYSTEM as _SUMMARY_SYSTEM,
    KIA_SUMMARY_PAGE_USER_SMALL as _SUMMARY_USER_SMALL,
    KIA_SUMMARY_PAGE_USER_LARGE as _SUMMARY_USER_LARGE,
    KIA_SUMMARY_PAGE_BATCH_USER as _SUMMARY_BATCH_USER,
    KIA_MINDMAP_PROMPT,
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
)

@celery_app.task(bind=True, name="kia.reindex_all_sources", queue="kia")
def run_reindex_all_sources(self):
    """Re-embed all existing KI-Assistent chunks with the current embedding provider.

    Triggered by admin after an embedding-model change. Preserves source UUIDs,
    file paths, chunk IDs and page numbers — so chips/notes/tools stay intact.
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

    module_ids_seen: set[int] = set()
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
            module_ids_seen.add(source["module_id"])
        except Exception as e:
            failed += 1
            logger.error("KI Tutor reindex: source {} failed: {}", source_uuid, e)
            db.update_aia_source_status(source_uuid, "failed", error_message=str(e))
        finally:
            done += 1
            _set_progress(filename, failed=failed)

    # Bump fingerprint on every touched module so the new provider is recorded
    for module_id in module_ids_seen:
        module = db.get_aia_module_by_id(module_id)
        if module:
            db.update_aia_module_status(
                module["uuid"], "ready",
                embedding_model=embedding_model,
                embedding_fingerprint=fingerprint,
            )

    db.set_setting("reindex_progress", _json.dumps({
        "total": total, "done": done, "current": "done", "failed": failed,
        "running": False,
    }))
    logger.info("KI Tutor reindex: finished ({} ok, {} failed)", done - failed, failed)

