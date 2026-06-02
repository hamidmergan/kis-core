"""KI-Assistent Celery tasks - source indexing + media transcription."""

import os

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import open_input_file

from src.features.ai_assistant.tasks._helpers import _format_ts


def _save_transcript_artifact(key: str, text: str) -> None:
    """Write a transcript-related text artifact to the same backend as the source file."""
    from src.storage import USE_S3
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=text.encode("utf-8"))
    else:
        from pathlib import Path as _Path
        _Path(key).write_text(text, encoding="utf-8")

@celery_app.task(bind=True, name="aia.index_source", queue="aia")
def run_index_source(self, source_uuid: str, locale: str = "de"):
    try:
        # 1. Load source from DB
        source = db.get_aia_source(source_uuid)
        if source is None:
            raise RuntimeError(f"Source not found: {source_uuid}")

        source_id = source["id"]
        workspace_id = source["workspace_id"]
        file_path_stored = source["file_path"]
        file_type = source["file_type"]
        filename = source["filename"]

        # 2. Status → indexing
        db.update_aia_source_status(source_uuid, "indexing")
        logger.info("KI Tutor: indexing source {} ({})", source_uuid, filename)

        # 3. Embedding provider + fingerprint
        from src.services.aia_embeddings import get_embedding_provider, compute_fingerprint
        provider = get_embedding_provider()
        fingerprint = compute_fingerprint(provider)

        _en_translation_pending = False

        embedding_model = provider.model_name

        # 4. Fetch file from storage
        import os
        suffix = os.path.splitext(filename)[1] or f".{file_type}"
        media_language: str | None = None
        with open_input_file(file_path_stored, suffix=suffix) as local_path:
            # 5. Extract chunks (branch: media vs document)
            from src.services import aia_chunker
            media_duration: float | None = None

            if aia_chunker.is_media_file(file_type):
                # Audio/Video: transcribe with timestamps, then chunk
                from src.services.subtitle_converter import segments_to_vtt
                from src.dependencies import resolve_whisper_client
                whisper_client = resolve_whisper_client()
                logger.info("KI Tutor: transcribing media source {} ({})", source_uuid, filename)
                segments, media_duration, media_language = whisper_client.transcribe_chunked_verbose(
                    local_path, cache_key=source_uuid
                )
                if not segments:
                    raise RuntimeError("Whisper returned no segments for this audio/video file.")
                chunks = aia_chunker.segments_to_chunks(segments)

                # Save full transcript as .txt next to the source file
                transcript_text = "\n".join(
                    f"[{_format_ts(s['start'])} - {_format_ts(s['end'])}] {s['text']}"
                    for s in segments
                )
                base_key = file_path_stored.rsplit(".", 1)[0]
                transcript_key = base_key + "_transcript.txt"
                _save_transcript_artifact(transcript_key, transcript_text)
                logger.info("KI Tutor: transcript saved to {}", transcript_key)

                # Save VTT in source language (e.g. _transcript.de.vtt)
                lang_code = (media_language or "").lower() or "unknown"
                source_vtt_key = f"{base_key}_transcript.{lang_code}.vtt"
                _save_transcript_artifact(source_vtt_key, segments_to_vtt(segments))
                logger.info("KI Tutor: VTT ({}) saved to {}", lang_code, source_vtt_key)

                # English VTT is produced by a separate Celery task dispatched at the
                # end of this task (after chunking/embedding) so chat is available
                # before translation finishes.
                _en_translation_pending = lang_code not in ("en", "unknown")
            else:
                def _progress_cb(stage: str, page: int | None = None, total: int | None = None) -> None:
                    db.update_aia_source_progress(source_uuid, stage, page=page, total=total)
                chunks = aia_chunker.extract_chunks(local_path, file_type, progress_cb=_progress_cb)

            # 6. Save chunks to DB
            db.update_aia_source_progress(source_uuid, "chunking")
            chunk_ids: list[int] = []
            for chunk in chunks:
                chunk_id = db.create_aia_chunk(
                    source_id=source_id,
                    page_number=chunk["page_number"],
                    content=chunk["content"],
                    start_time=chunk.get("start_time"),
                    end_time=chunk.get("end_time"),
                )
                chunk_ids.append(chunk_id)

            # 7. Embed chunks in batches of 20
            db.update_aia_source_progress(source_uuid, "embedding")
            _EMBED_BATCH = 20
            for i in range(0, len(chunks), _EMBED_BATCH):
                batch_chunks = chunks[i: i + _EMBED_BATCH]
                batch_ids = chunk_ids[i: i + _EMBED_BATCH]
                texts = [c["content"] for c in batch_chunks]
                vectors = provider.embed(texts)
                for chunk_id, vector in zip(batch_ids, vectors):
                    db.update_chunk_embedding(chunk_id, vector)
                logger.info(
                    "KI Tutor: embedded chunks {}-{}/{} for source {}",
                    i + 1, i + len(batch_chunks), len(chunks), source_uuid,
                )

        # 8. Source status → ready
        db.update_aia_source_status(
            source_uuid,
            "ready",
            chunk_count=len(chunks),
            embedding_model=embedding_model,
            duration=media_duration,
            language=media_language,
        )
        logger.info("KI Tutor: source {} indexed ({} chunks)", source_uuid, len(chunks))

        # 9. Check if all non-failed sources for this workspace are ready → set workspace ready
        sources = db.get_aia_sources_by_workspace(workspace_id)
        non_failed = [s for s in sources if s["status"] != "failed"]
        all_ready = len(non_failed) > 0 and all(s["status"] == "ready" for s in non_failed)
        if all_ready:
            workspace = db.get_aia_workspace_by_id(workspace_id)
            if workspace:
                db.update_aia_workspace_status(
                    workspace["uuid"],
                    "ready",
                    embedding_model=embedding_model,
                    embedding_fingerprint=fingerprint,
                )
                logger.info("KI Tutor: workspace {} is now ready", workspace["uuid"])

        # 10. Dispatch non-critical follow-ups (EN translation runs relaxed in bg).
        # Mode is owner-controlled per workspace (default "manual"): only "auto"
        # triggers at ingest; "manual" waits for the button; "off" disables it.
        if _en_translation_pending:
            workspace = db.get_aia_workspace_by_id(workspace_id)
            translation_mode = (workspace or {}).get("transcript_translation_mode", "manual")
            if translation_mode == "auto":
                from src.services import feature_router
                try:
                    binding = feature_router.resolve("transcript_translate")
                    run_translate_transcript_en.delay(source_uuid, binding.provider["id"])
                    logger.info(
                        "KI Tutor: dispatched EN translation for {} (provider_id={})",
                        source_uuid, binding.provider["id"],
                    )
                except feature_router.FeatureNotConfigured:
                    logger.warning(
                        "KI Tutor: transcript_translate not configured, skipping auto EN translation for {}",
                        source_uuid,
                    )
            else:
                logger.info(
                    "KI Tutor: skipping EN auto-translation for {} (mode={})",
                    source_uuid, translation_mode,
                )

        # 11. No summaries (pgvector-only design). Both chat paths run on
        # retrieval: SPECIFIC = hybrid search, GENERIC = multi-query retrieval
        # (see routes/chat.py). The source is fully usable the moment indexing
        # finishes; clear the progress field so the card shows ready.
        db.clear_aia_source_progress(source_uuid)

    except Exception as e:
        from src.services.aia_chunker import PdfNoReadableTextError
        from src.i18n import t

        # Rate-limit / transient upstream → keep status, requeue task with backoff.
        # Already-transcribed chunks are cached per source_uuid in Redis, so the
        # retry skips them and only re-tries the chunk that failed.
        msg = str(e).lower()
        is_rate_limit = "429" in msg or "rate limit" in msg
        if is_rate_limit and self.request.retries < 5:
            countdown = min(30 * (2 ** self.request.retries), 120)  # 30s, 1m, 2m, 2m, 2m (capped)
            logger.warning(
                "KI Tutor: source {} hit rate limit (attempt {}/{}), retrying in {}s",
                source_uuid, self.request.retries + 1, 5, countdown,
            )
            raise self.retry(exc=e, countdown=countdown, max_retries=5)

        logger.error("KI Tutor: indexing source {} failed: {}", source_uuid, e)
        if isinstance(e, PdfNoReadableTextError):
            error_message = t("ai.source.pdfNoReadableText", locale)
        else:
            error_message = str(e)
        db.update_aia_source_status(source_uuid, "failed", error_message=error_message)
        raise


@celery_app.task(bind=True, name="aia.translate_transcript_en", queue="aia")
def run_translate_transcript_en(self, source_uuid: str, provider_id: int | None = None):
    """Translate a media source's source-language VTT to English.

    Runs as a follow-up to indexing so chat is available before translation completes.
    ``provider_id`` is resolved from the ``transcript_translate`` feature route.
    """
    try:
        return _run_translate_transcript_en_inner(source_uuid, provider_id)
    except Exception as e:
        msg = str(e).lower()
        is_rate_limit = "429" in msg or "rate limit" in msg
        if is_rate_limit and self.request.retries < 5:
            countdown = min(30 * (2 ** self.request.retries), 120)  # 30s..2m capped
            logger.warning(
                "KI Tutor EN-translate: source {} hit rate limit (attempt {}/{}), retrying in {}s",
                source_uuid, self.request.retries + 1, 5, countdown,
            )
            raise self.retry(exc=e, countdown=countdown, max_retries=5)
        logger.error("KI Tutor EN-translate: source {} failed: {}", source_uuid, e)
        raise


def _run_translate_transcript_en_inner(source_uuid: str, provider_id: int | None) -> None:
    from src.services.subtitle_converter import vtt_to_segments, segments_to_vtt
    from src.storage import file_exists, get_file
    from src.dependencies import get_translate_client_for_provider

    source = db.get_aia_source(source_uuid)
    if source is None:
        logger.warning("KI Tutor EN-translate: source {} not found, skipping", source_uuid)
        return

    base_key = source["file_path"].rsplit(".", 1)[0]
    en_key = f"{base_key}_transcript.en.vtt"
    if file_exists(en_key):
        logger.info("KI Tutor EN-translate: {} already exists, skipping", en_key)
        return

    # Locate the source-language VTT. Currently only German sources are auto-translated;
    # the loop leaves room for other ISO codes without restructuring.
    source_vtt_key: str | None = None
    source_lang: str | None = None
    for candidate_lang in ("de",):
        candidate_key = f"{base_key}_transcript.{candidate_lang}.vtt"
        if file_exists(candidate_key):
            source_vtt_key = candidate_key
            source_lang = candidate_lang
            break
    if not source_vtt_key or not source_lang:
        logger.warning(
            "KI Tutor EN-translate: no source VTT for {}, skipping", source_uuid
        )
        return

    segments = vtt_to_segments(get_file(source_vtt_key).decode("utf-8"))
    if not segments:
        logger.warning(
            "KI Tutor EN-translate: could not parse {}, skipping", source_vtt_key
        )
        return

    texts = [s["text"] for s in segments]
    lang_name_map = {"de": "German"}
    source_lang_name = lang_name_map.get(source_lang, source_lang)

    client, _glossary = get_translate_client_for_provider(provider_id)
    if client is None:
        raise RuntimeError(
            "transcript_translate: no translation provider configured — set one in the admin KI panel"
        )

    # DeepLClient expects ISO codes ("DE", "EN-US"); LLMTranslationClient uses
    # human-readable names embedded in the prompt ("German", "English").
    from src.services.deepl_client import DeepLClient

    if isinstance(client, DeepLClient):
        translated: list[str] = client.translate_batch(
            texts, source_lang=source_lang.upper(), target_lang="EN-US",
        )
    else:
        translated = client.translate_batch(
            texts, source_lang=source_lang_name, target_lang="English",
        )

    en_segments = [
        {"start": s["start"], "end": s["end"], "text": t_text}
        for s, t_text in zip(segments, translated)
    ]
    _save_transcript_artifact(en_key, segments_to_vtt(en_segments))
    logger.info(
        "KI Tutor EN-translate: saved {} ({} segments via provider_id={})",
        en_key, len(en_segments), provider_id,
    )
