"""KI-Assistent Celery tasks - source indexing + paragraph summaries."""

import concurrent.futures
import os
import re

from langfuse.decorators import langfuse_context, observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import open_input_file
from src.limits import (
    AIA_SUMMARY_PARALLEL_WORKERS_LARGE,
    AIA_SUMMARY_BATCH_SIZE,
)
from src.tool_prompts import AIA_MINDMAP_PROMPT

from src.features.ai_assistant.tasks._helpers import (
    _format_ts,
    _save_aia_output,
    _detect_language,
    _summarize_batch,
    _get_llm_client,
    _clean_llm_json,
    generate_doc_summary,
)


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
                    run_translate_transcript_en.delay(source_uuid, binding["provider_id"])
                    logger.info(
                        "KI Tutor: dispatched EN translation for {} (provider_id={})",
                        source_uuid, binding["provider_id"],
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

        # 11. Summary pipeline. PDFs get page-summaries first (UI panel + better
        # doc-summary input); the page-summary task chains doc-summary at its end.
        # Non-PDFs (audio/video/docx/pptx/txt) have no page-summary concept, so
        # doc-summary runs directly from their chunks.
        # Pre-set the next stage on the source itself so the UI keeps the
        # spinner visible during the Celery queue gap. Without this, status
        # is "ready" with progress=NULL for a few seconds before the chained
        # task runs - the source would look fully done in the UI even though
        # the summaries haven't started yet.
        if source["file_type"] == "pdf":
            from src.tasks.aia_tasks import run_generate_summaries
            db.update_aia_source_progress(source_uuid, "page_summaries")
            run_generate_summaries.delay(source_uuid, locale)
            logger.info("KI Tutor: dispatched page-summaries for {}", source_uuid)
        else:
            db.update_aia_source_progress(source_uuid, "doc_summary")
            run_generate_doc_summary.delay(source_uuid)
            logger.info("KI Tutor: dispatched doc-summary for {}", source_uuid)

    except Exception as e:
        from src.services.aia_chunker import PdfNoReadableTextError
        from src.i18n import t

        # Rate-limit / transient upstream → keep status, requeue task with backoff.
        # Already-transcribed chunks are cached per source_uuid in Redis, so the
        # retry skips them and only re-tries the chunk that failed.
        msg = str(e).lower()
        is_rate_limit = "429" in msg or "rate limit" in msg
        if is_rate_limit and self.request.retries < 5:
            countdown = 60 * (2 ** self.request.retries)  # 60s, 2m, 4m, 8m, 16m
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

@celery_app.task(bind=True, name="aia.generate_doc_summary", queue="aia")
def run_generate_doc_summary(self, source_uuid: str):
    """Generate the English doc-level summary for a source.

    Soft-failure: any error is logged but never marks the source itself as
    failed - the doc-summary is an optional retrieval aid, chat and reader
    still work without it.
    """
    try:
        generate_doc_summary(source_uuid)
    except Exception as e:
        msg = str(e).lower()
        if "429" in msg or "rate limit" in msg:
            if self.request.retries < 3:
                countdown = 60 * (2 ** self.request.retries)  # 1m, 2m, 4m
                logger.warning(
                    "KI Tutor doc-summary: {} rate limited (attempt {}/3), retry in {}s",
                    source_uuid, self.request.retries + 1, countdown,
                )
                raise self.retry(exc=e, countdown=countdown, max_retries=3)
        logger.warning("KI Tutor doc-summary: {} failed, will retry on next reindex: {}", source_uuid, e)


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
            countdown = 60 * (2 ** self.request.retries)
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


@celery_app.task(bind=True, name="aia.generate_summaries", queue="aia")
@observe(name="aia-summaries")
def run_generate_summaries(self, source_uuid: str, locale: str = "de"):
    """Generate AI page-level summaries for a PDF source.

    `locale` is the workspace owner's UI locale, used to pick the meta-page
    sentinel ("Keine Zusammenfassung vorhanden" / "No summary available").
    Defaults to 'de' so older callsites (and pre-i18n queued jobs) keep working.
    """
    try:
        source = db.get_aia_source(source_uuid)
        if source is None:
            raise RuntimeError(f"Source not found: {source_uuid}")

        if source["file_type"] != "pdf":
            return

        db.update_aia_source_summaries_status(source_uuid, "generating")
        db.update_aia_source_progress(source_uuid, "page_summaries")
        logger.info("KI Tutor: generating page summaries for source {}", source_uuid)

        # 1. Build page texts from existing chunks in DB (no need to re-read PDF)
        chunks = db.get_aia_chunks_by_source(source["id"])
        if not chunks:
            db.update_aia_source_summaries_status(source_uuid, "ready")
            logger.info("KI Tutor: no chunks found for {}", source_uuid)
            return

        page_map: dict[int, list[str]] = {}
        for c in chunks:
            pn = c["page_number"]
            if pn not in page_map:
                page_map[pn] = []
            page_map[pn].append(c["content"])

        pages = [
            {"page_number": pn, "content": "\n".join(texts)}
            for pn, texts in sorted(page_map.items())
        ]

        # 2. Detect language
        sample = " ".join(p["content"][:200] for p in pages[:3])
        lang = _detect_language(sample)

        # 3. Build LLM client
        from langfuse.openai import OpenAI
        from src.dependencies import _resolve_llm_provider
        _api_key, _base_url, _model, _provider = _resolve_llm_provider()
        client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=90)
        model = _model
        extra_body = {}
        langfuse_context.update_current_observation(
            metadata={"provider": _provider, "base_url": _base_url, "model": model},
        )

        # 4. Skip pages that already have summaries (resume after partial failure)
        existing = db.get_page_summaries_by_source(source["id"])
        existing_pages = {s["page_number"] for s in existing}
        remaining_pages = [p for p in pages if p["page_number"] not in existing_pages]

        if not remaining_pages:
            db.update_aia_source_summaries_status(source_uuid, "ready")
            db.clear_aia_source_progress(source_uuid)
            logger.info("KI Tutor: all pages already summarized for {}", source_uuid)
            return

        logger.info(
            "KI Tutor: {} of {} pages need summaries for {}",
            len(remaining_pages), len(pages), source_uuid,
        )

        # 5. Generate summaries in batches, save each batch immediately to DB
        def _save_page_summaries(page_batch: list[dict], summary_batch: list[str]):
            db.bulk_create_page_summaries(
                source_id=source["id"],
                summaries=[
                    {"page_number": p["page_number"], "summary": s}
                    for p, s in zip(page_batch, summary_batch)
                    if s.strip()
                ],
            )

        batches = [remaining_pages[i:i + AIA_SUMMARY_BATCH_SIZE] for i in range(0, len(remaining_pages), AIA_SUMMARY_BATCH_SIZE)]
        failed_batches = 0
        rate_limited = False

        with concurrent.futures.ThreadPoolExecutor(max_workers=AIA_SUMMARY_PARALLEL_WORKERS_LARGE) as executor:
            futures = {
                executor.submit(_summarize_batch, client, model, batch, lang, locale): i
                for i, batch in enumerate(batches)
            }
            for future in concurrent.futures.as_completed(futures):
                bidx = futures[future]
                batch = batches[bidx]
                try:
                    summaries = future.result()
                    _save_page_summaries(batch, summaries)
                    start = batch[0]["page_number"]
                    end = batch[-1]["page_number"]
                    logger.info(
                        "KI Tutor: summarized pages {}-{} for source {} (saved)",
                        start, end, source_uuid,
                    )
                except Exception as exc:
                    if "429" in str(exc):
                        rate_limited = True
                        logger.warning("KI Tutor: rate limited for {} - aborting remaining batches", source_uuid)
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    failed_batches += 1
                    logger.warning("KI Tutor: batch {} failed for {}: {}", bidx + 1, source_uuid, exc)

        # 6. Set status based on results
        if rate_limited:
            if self.request.retries < 5:
                countdown = 60 * (2 ** self.request.retries)  # 1m, 2m, 4m, 8m, 16m
                logger.warning(
                    "KI Tutor: summary rate limited for {} - saved partial results, retrying in {}s (attempt {}/{})",
                    source_uuid, countdown, self.request.retries + 1, 5,
                )
                raise self.retry(countdown=countdown, max_retries=5)
            db.update_aia_source_summaries_status(source_uuid, "rate_limited")
            db.clear_aia_source_progress(source_uuid)
            logger.warning("KI Tutor: rate limited for {} - max retries exhausted, manual retry available", source_uuid)
        elif failed_batches > 0:
            db.update_aia_source_summaries_status(source_uuid, "failed")
            db.clear_aia_source_progress(source_uuid)
            logger.warning(
                "KI Tutor: {} batch(es) failed for {} - saved partial results, retry will resume",
                failed_batches, source_uuid,
            )
        else:
            db.update_aia_source_summaries_status(source_uuid, "ready")
            db.update_aia_source_progress(source_uuid, "doc_summary")
            logger.info("KI Tutor: page summaries ready for source {} ({} pages)", source_uuid, len(pages))
            # Chain doc-summary now that page-summaries are available - it'll use
            # them as compact input (instead of falling back to truncated chunks).
            run_generate_doc_summary.delay(source_uuid)
            logger.info("KI Tutor: dispatched doc-summary for {} (from page-summaries)", source_uuid)

    except Exception as e:
        from celery.exceptions import Retry
        if isinstance(e, Retry):
            raise  # let Celery process the retry; do not overwrite status
        err_str = str(e)
        is_rate_limit = "429" in err_str or "rate" in err_str.lower()
        if is_rate_limit and self.request.retries < 5:
            countdown = 60 * (2 ** self.request.retries)
            logger.warning(
                "KI Tutor: summary task hit rate limit before batch loop for {} (attempt {}/{}), retrying in {}s",
                source_uuid, self.request.retries + 1, 5, countdown,
            )
            raise self.retry(exc=e, countdown=countdown, max_retries=5)
        status = "rate_limited" if is_rate_limit else "failed"
        logger.error("KI Tutor: summary generation {} for {}: {}", status, source_uuid, e)
        db.update_aia_source_summaries_status(source_uuid, status)
        db.clear_aia_source_progress(source_uuid)

