"""KI-Assistent Celery tasks — source indexing + paragraph summaries."""

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

from src.features.ki_assistent.tasks._helpers import (
    _format_ts,
    _save_kia_output,
    _detect_language,
    _parse_numbered_summaries,
    _clean_summary,
    _call_llm_with_retry,
    _summarize_page,
    _summarize_batch,
    _get_llm_client,
    _clean_llm_json,
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

@celery_app.task(bind=True, name="kia.index_source", queue="kia")
def run_index_source(self, source_uuid: str):
    try:
        # 1. Load source from DB
        source = db.get_kia_source(source_uuid)
        if source is None:
            raise RuntimeError(f"Source not found: {source_uuid}")

        source_id = source["id"]
        module_id = source["module_id"]
        file_path_stored = source["file_path"]
        file_type = source["file_type"]
        filename = source["filename"]

        # 2. Status → indexing
        db.update_kia_source_status(source_uuid, "indexing")
        logger.info("KI Tutor: indexing source {} ({})", source_uuid, filename)

        # 3. Embedding provider + fingerprint
        from src.services.kia_embeddings import get_embedding_provider, compute_fingerprint
        provider = get_embedding_provider()
        fingerprint = compute_fingerprint(provider)

        from src.config import Settings
        _s = Settings()
        embedding_model = _s.ollama_embedding_model if _s.tutor_embedding_provider == "ollama" else _s.kisski_embedding_model

        # 4. Fetch file from storage
        import os
        suffix = os.path.splitext(filename)[1] or f".{file_type}"
        media_language: str | None = None
        with open_input_file(file_path_stored, suffix=suffix) as local_path:
            # 5. Extract chunks (branch: media vs document)
            from src.services import kia_chunker
            media_duration: float | None = None

            if kia_chunker.is_media_file(file_type):
                # Audio/Video: transcribe with timestamps, then chunk
                from src.services.kisski_client import KisskiClient
                from src.services.subtitle_converter import segments_to_vtt
                from src.dependencies import _resolve_llm_provider
                _api_key, _base_url, _model, _provider = _resolve_llm_provider()
                if not _api_key:
                    raise RuntimeError("Kein LLM-Provider konfiguriert (für Whisper-Transkription)")
                whisper_client = KisskiClient(
                    api_key=_api_key, base_url=_base_url, model=_model, provider=_provider,
                )
                logger.info("KI Tutor: transcribing media source {} ({})", source_uuid, filename)
                segments, media_duration, media_language = whisper_client.transcribe_chunked_verbose(local_path)
                if not segments:
                    raise RuntimeError("Whisper returned no segments for this audio/video file.")
                chunks = kia_chunker.segments_to_chunks(segments)

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

                # Additionally produce an English VTT via Whisper translate task
                # (skipped if the audio is already English).
                if lang_code != "en":
                    try:
                        en_segments = whisper_client.translate_chunked_verbose(local_path)
                        if en_segments:
                            en_vtt_key = f"{base_key}_transcript.en.vtt"
                            _save_transcript_artifact(en_vtt_key, segments_to_vtt(en_segments))
                            logger.info("KI Tutor: EN VTT saved to {}", en_vtt_key)
                    except Exception as e:
                        logger.warning(
                            "KI Tutor: EN translation VTT failed for {}: {}", source_uuid, e
                        )
            else:
                chunks = kia_chunker.extract_chunks(local_path, file_type)

            # 6. Save chunks to DB
            chunk_ids: list[int] = []
            for chunk in chunks:
                chunk_id = db.create_kia_chunk(
                    source_id=source_id,
                    page_number=chunk["page_number"],
                    content=chunk["content"],
                    start_time=chunk.get("start_time"),
                    end_time=chunk.get("end_time"),
                )
                chunk_ids.append(chunk_id)

            # 7. Embed chunks in batches of 20
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
        db.update_kia_source_status(
            source_uuid,
            "ready",
            chunk_count=len(chunks),
            embedding_model=embedding_model,
            duration=media_duration,
            language=media_language,
        )
        logger.info("KI Tutor: source {} indexed ({} chunks)", source_uuid, len(chunks))

        # 9. Check if all non-failed sources for this module are ready → set module ready
        sources = db.get_kia_sources_by_module(module_id)
        non_failed = [s for s in sources if s["status"] != "failed"]
        all_ready = len(non_failed) > 0 and all(s["status"] == "ready" for s in non_failed)
        if all_ready:
            module = db.get_kia_module_by_id(module_id)
            if module:
                db.update_kia_module_status(
                    module["uuid"],
                    "ready",
                    embedding_model=embedding_model,
                    embedding_fingerprint=fingerprint,
                )
                logger.info("KI Tutor: module {} is now ready", module["uuid"])

        # 10. Trigger paragraph summary generation (async, non-blocking)
        if file_type == "pdf":
            run_generate_summaries.delay(source_uuid)

    except Exception as e:
        logger.error("KI Tutor: indexing source {} failed: {}", source_uuid, e)
        db.update_kia_source_status(source_uuid, "failed", error_message=str(e))
        raise

@celery_app.task(bind=True, name="kia.generate_summaries", queue="kia")
@observe(name="kia-summaries")
def run_generate_summaries(self, source_uuid: str):
    """Generate AI page-level summaries for a PDF source."""
    try:
        source = db.get_kia_source(source_uuid)
        if source is None:
            raise RuntimeError(f"Source not found: {source_uuid}")

        if source["file_type"] != "pdf":
            return

        db.update_kia_source_summaries_status(source_uuid, "generating")
        logger.info("KI Tutor: generating page summaries for source {}", source_uuid)

        # 1. Extract text per page
        import os
        suffix = os.path.splitext(source["filename"])[1] or ".pdf"
        with open_input_file(source["file_path"], suffix=suffix) as local_path:
            from src.services.kia_chunker import extract_page_texts
            pages = extract_page_texts(local_path)

        if not pages:
            db.update_kia_source_summaries_status(source_uuid, "ready")
            logger.info("KI Tutor: no pages with text found for {}", source_uuid)
            return

        # 2. Detect language
        sample = " ".join(p["content"][:200] for p in pages[:3])
        lang = _detect_language(sample)

        # 3. Build LLM client
        from langfuse.openai import OpenAI
        from src.dependencies import _resolve_llm_provider
        _api_key, _base_url, _model, _provider = _resolve_llm_provider()
        client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=90)
        model = _model
        # Always use single-page summaries (batch mode causes LLMs to mix up page content)
        is_small = True
        extra_body = {}
        langfuse_context.update_current_observation(
            metadata={"provider": _provider, "base_url": _base_url, "model": model},
        )

        # 4. Skip pages that already have summaries (resume after partial failure)
        existing = db.get_paragraph_summaries_by_source(source["id"])
        existing_pages = {s["page_number"] for s in existing}
        remaining_pages = [p for p in pages if p["page_number"] not in existing_pages]

        if not remaining_pages:
            db.update_kia_source_summaries_status(source_uuid, "ready")
            logger.info("KI Tutor: all pages already summarized for {}", source_uuid)
            return

        logger.info(
            "KI Tutor: {} of {} pages need summaries for {}",
            len(remaining_pages), len(pages), source_uuid,
        )

        # 5. Generate summaries — save each batch/page immediately to DB
        #    Small models (ollama): parallel single-page requests
        #    Large models (cloud):  parallel batches of KIA_SUMMARY_BATCH_SIZE pages
        def _save_page_summaries(page_batch: list[dict], summary_batch: list[str]):
            """Save a batch of summaries to DB immediately."""
            db.bulk_create_paragraph_summaries(
                source_id=source["id"],
                summaries=[
                    {
                        "page_number": p["page_number"],
                        "block_index": 0,
                        "bbox": {"x0": 0, "y0": 0, "x1": 0, "y1": 0},
                        "content": p["content"][:500],
                        "summary": s,
                    }
                    for p, s in zip(page_batch, summary_batch)
                    if s.strip()
                ],
            )

        failed_batches = 0

        if is_small:
            with concurrent.futures.ThreadPoolExecutor(max_workers=KIA_SUMMARY_PARALLEL_WORKERS_SMALL) as executor:
                futures = {
                    executor.submit(_summarize_page, client, model, p, True, extra_body, lang): i
                    for i, p in enumerate(remaining_pages)
                }
                for future in concurrent.futures.as_completed(futures):
                    idx = futures[future]
                    try:
                        summary = future.result()
                        _save_page_summaries([remaining_pages[idx]], [summary])
                        logger.info(
                            "KI Tutor: summarized page {}/{} for source {}",
                            idx + 1, len(remaining_pages), source_uuid,
                        )
                    except Exception as exc:
                        failed_batches += 1
                        logger.warning("KI Tutor: page {} failed for {}: {}", idx + 1, source_uuid, exc)
        else:
            batches = [remaining_pages[i:i + KIA_SUMMARY_BATCH_SIZE] for i in range(0, len(remaining_pages), KIA_SUMMARY_BATCH_SIZE)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=KIA_SUMMARY_PARALLEL_WORKERS_LARGE) as executor:
                futures = {
                    executor.submit(_summarize_batch, client, model, batch, lang): i
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
                        failed_batches += 1
                        logger.warning("KI Tutor: batch {} failed for {}: {}", bidx + 1, source_uuid, exc)

        # 6. Set status based on results
        if failed_batches > 0:
            db.update_kia_source_summaries_status(source_uuid, "failed")
            logger.warning(
                "KI Tutor: {} batch(es) failed for {} — saved partial results, retry will resume",
                failed_batches, source_uuid,
            )
        else:
            db.update_kia_source_summaries_status(source_uuid, "ready")
            logger.info("KI Tutor: page summaries ready for source {} ({} pages)", source_uuid, len(pages))

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "rate" in err_str.lower():
            status = "rate_limited"
        else:
            status = "failed"
        logger.error("KI Tutor: summary generation {} for {}: {}", status, source_uuid, e)
        db.update_kia_source_summaries_status(source_uuid, status)

