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
    KIA_SUMMARY_PARALLEL_WORKERS_LARGE,
    KIA_SUMMARY_BATCH_SIZE,
)
from src.tool_prompts import KIA_MINDMAP_PROMPT

from src.features.ai_assistant.tasks._helpers import (
    _format_ts,
    _save_aia_output,
    _detect_language,
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
                segments, media_duration, media_language = whisper_client.transcribe_chunked_verbose(local_path)
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
                chunks = aia_chunker.extract_chunks(local_path, file_type)

            # 6. Save chunks to DB
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
                translation_provider = db.get_setting(
                    "transcript_translation_provider", "llm"
                )
                run_translate_transcript_en.delay(source_uuid, translation_provider)
                logger.info(
                    "KI Tutor: dispatched EN translation for {} (provider={})",
                    source_uuid, translation_provider,
                )
            else:
                logger.info(
                    "KI Tutor: skipping EN auto-translation for {} (mode={})",
                    source_uuid, translation_mode,
                )

        # 11. Summaries are generated on-demand via button in PDF viewer

    except Exception as e:
        logger.error("KI Tutor: indexing source {} failed: {}", source_uuid, e)
        db.update_aia_source_status(source_uuid, "failed", error_message=str(e))
        raise

@celery_app.task(bind=True, name="kia.translate_transcript_en", queue="kia")
def run_translate_transcript_en(self, source_uuid: str, provider: str = "deepl"):
    """Translate a media source's source-language VTT to English.

    Runs as a follow-up to indexing so chat is available before translation completes.
    ``provider`` is ``"deepl"`` (fast, quota-limited) or ``"llm"`` (via KISSKI chat,
    used as manual fallback when DeepL's free-tier quota is exhausted).
    """
    from src.services.subtitle_converter import vtt_to_segments, segments_to_vtt
    from src.storage import file_exists, get_file

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

    if provider == "llm":
        from src.services.llm_translation_client import LLMTranslationClient
        from src.dependencies import _resolve_llm_provider
        api_key, base_url, model, prov = _resolve_llm_provider()
        if not api_key:
            raise RuntimeError("Kein LLM-Provider konfiguriert")
        client = LLMTranslationClient(
            api_key=api_key, base_url=base_url, model=model, provider=prov,
        )
        # Chunk to keep each batch below the client's 4096 output-token cap -
        # larger batches truncate and trigger slow one-by-one fallback.
        _LLM_CHUNK = 30
        translated: list[str] = []
        for start in range(0, len(texts), _LLM_CHUNK):
            chunk = texts[start:start + _LLM_CHUNK]
            translated.extend(client.translate_batch(
                chunk, source_lang=source_lang_name, target_lang="English",
            ))
            logger.info(
                "KI Tutor EN-translate: LLM progress {}/{} segments",
                min(start + _LLM_CHUNK, len(texts)), len(texts),
            )
    else:  # deepl
        from src.dependencies import get_deepl_client
        deepl_client = get_deepl_client()
        if deepl_client is None:
            raise RuntimeError("DeepL ist nicht konfiguriert")
        translated = deepl_client.translate_batch(
            texts, source_lang=source_lang.upper(), target_lang="EN-US",
        )

    en_segments = [
        {"start": s["start"], "end": s["end"], "text": t}
        for s, t in zip(segments, translated)
    ]
    _save_transcript_artifact(en_key, segments_to_vtt(en_segments))
    logger.info(
        "KI Tutor EN-translate: saved {} ({} segments via {})",
        en_key, len(en_segments), provider,
    )


@celery_app.task(bind=True, name="kia.generate_summaries", queue="kia")
@observe(name="kia-summaries")
def run_generate_summaries(self, source_uuid: str):
    """Generate AI page-level summaries for a PDF source."""
    try:
        source = db.get_aia_source(source_uuid)
        if source is None:
            raise RuntimeError(f"Source not found: {source_uuid}")

        if source["file_type"] != "pdf":
            return

        db.update_aia_source_summaries_status(source_uuid, "generating")
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
        existing = db.get_paragraph_summaries_by_source(source["id"])
        existing_pages = {s["page_number"] for s in existing}
        remaining_pages = [p for p in pages if p["page_number"] not in existing_pages]

        if not remaining_pages:
            db.update_aia_source_summaries_status(source_uuid, "ready")
            logger.info("KI Tutor: all pages already summarized for {}", source_uuid)
            return

        logger.info(
            "KI Tutor: {} of {} pages need summaries for {}",
            len(remaining_pages), len(pages), source_uuid,
        )

        # 5. Generate summaries in batches, save each batch immediately to DB
        def _save_page_summaries(page_batch: list[dict], summary_batch: list[str]):
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

        batches = [remaining_pages[i:i + KIA_SUMMARY_BATCH_SIZE] for i in range(0, len(remaining_pages), KIA_SUMMARY_BATCH_SIZE)]
        failed_batches = 0
        rate_limited = False

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
                    if "429" in str(exc):
                        rate_limited = True
                        logger.warning("KI Tutor: rate limited for {} - aborting remaining batches", source_uuid)
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    failed_batches += 1
                    logger.warning("KI Tutor: batch {} failed for {}: {}", bidx + 1, source_uuid, exc)

        # 6. Set status based on results
        if rate_limited:
            db.update_aia_source_summaries_status(source_uuid, "rate_limited")
            logger.warning("KI Tutor: rate limited for {} - saved partial results, user can retry", source_uuid)
        elif failed_batches > 0:
            db.update_aia_source_summaries_status(source_uuid, "failed")
            logger.warning(
                "KI Tutor: {} batch(es) failed for {} - saved partial results, retry will resume",
                failed_batches, source_uuid,
            )
        else:
            db.update_aia_source_summaries_status(source_uuid, "ready")
            logger.info("KI Tutor: page summaries ready for source {} ({} pages)", source_uuid, len(pages))

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "rate" in err_str.lower():
            status = "rate_limited"
        else:
            status = "failed"
        logger.error("KI Tutor: summary generation {} for {}: {}", status, source_uuid, e)
        db.update_aia_source_summaries_status(source_uuid, status)

