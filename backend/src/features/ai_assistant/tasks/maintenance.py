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
