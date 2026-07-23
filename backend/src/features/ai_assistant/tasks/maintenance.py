"""KI-Assistent Celery tasks - reindex sources after embedding-model changes."""

from loguru import logger

from src.celery_app import celery_app
from src import database as db

@celery_app.task(bind=True, name="aia.reindex_all_sources", queue="aia")
def run_reindex_all_sources(self):
    """Re-embed all existing KI-Assistent chunks with the current embedding provider.

    Triggered by admin after an embedding-model change. Preserves source UUIDs,
    file paths, chunk IDs and page numbers - so chips/notes/tools stay intact.
    Only the embedding vectors are replaced.
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
