"""KI-Assistent Celery tasks - source indexing + media transcription."""

import os
import time

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import (
    aia_transcript_key,
    aia_transcript_prefix,
    aia_vtt_key,
    list_keys,
    open_input_file,
)

from src.features.ai_assistant.tasks._helpers import _format_ts

# DOC SUMMARY at ingest is currently UNUSED: nothing reads aia_sources.summary (verified across
# chat, backend logic and frontend) — it was built for the not-yet-wired "GENERIC over summaries"
# Phase 2. Disabled so uploads don't burn map-reduce LLM calls for a dead artifact. The block in
# run_index_source is kept intact; set this True to re-enable (or when Phase 2 lands). Existing
# stored summaries are NOT touched.
_BUILD_INGEST_SUMMARY = False


def _save_transcript_artifact(key: str, text: str) -> None:
    """Write a transcript-related text artifact to the same backend as the source file."""
    from src import storage
    storage.put_bytes(key, text.encode("utf-8"))

@celery_app.task(bind=True, name="aia.index_source", queue="aia")
def run_index_source(self, source_uuid: str, locale: str = "de", _aia_job_uuid: str | None = None):
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

        # 3. Embedding provider. The drift-detection fingerprint {model, dim} is built
        # WITHOUT a probe call: the dimension is read for free from the first chunk vector
        # we embed below (len(vector)). compute_fingerprint kept only as a fallback for the
        # (pathological) chunks-but-no-vector case.
        from src.services.aia_embeddings import (
            get_embedding_provider, compute_fingerprint, fingerprint_from_dim,
        )
        provider = get_embedding_provider()
        fingerprint: str | None = None  # set from the first embedded batch (step 7)

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

                # Fragmented MP4 (fMP4) plays unreliably in the native <audio>/<video>
                # element — the browser skips whole ~fragment-length spans mid-stream,
                # which desyncs the transcript. Losslessly remux it to a progressive
                # faststart MP4 and overwrite the stored playback file (no re-encode, no
                # quality loss). Idempotent: a retry re-checks and skips an already-clean
                # file. Transcription then runs on the same normalised file.
                from src.services.media_normalize import normalize_if_fragmented
                media_path = local_path
                normalized_path = normalize_if_fragmented(local_path)
                if normalized_path:
                    from src.storage import put_file
                    put_file(file_path_stored, normalized_path)
                    media_path = normalized_path
                    logger.info(
                        "KI Tutor: normalized fragmented media {} -> progressive faststart",
                        source_uuid,
                    )

                whisper_client = resolve_whisper_client()
                logger.info("KI Tutor: transcribing media source {} ({})", source_uuid, filename)
                try:
                    segments, media_duration, media_language = whisper_client.transcribe_chunked_verbose(
                        media_path, cache_key=source_uuid
                    )
                finally:
                    if normalized_path:
                        os.unlink(normalized_path)
                if not segments:
                    raise RuntimeError("Whisper returned no segments for this audio/video file.")
                chunks = aia_chunker.segments_to_chunks(segments)

                # Save full transcript as .txt next to the source file
                transcript_text = "\n".join(
                    f"[{_format_ts(s['start'])} - {_format_ts(s['end'])}] {s['text']}"
                    for s in segments
                )
                transcript_key = aia_transcript_key(file_path_stored)
                _save_transcript_artifact(transcript_key, transcript_text)
                logger.info("KI Tutor: transcript saved to {}", transcript_key)

                # Save VTT in source language (e.g. _transcript.de.vtt)
                lang_code = (media_language or "").lower() or "unknown"
                source_vtt_key = aia_vtt_key(file_path_stored, lang_code)
                _save_transcript_artifact(source_vtt_key, segments_to_vtt(segments))
                logger.info("KI Tutor: VTT ({}) saved to {}", lang_code, source_vtt_key)

                # Ingest never translates. The translated VTT is produced by a
                # separate Celery task that only runs when someone asks for it in
                # the transcript panel (target language comes from the workspace).
            else:
                def _progress_cb(stage: str, page: int | None = None, total: int | None = None) -> None:
                    db.update_aia_source_progress(source_uuid, stage, page=page, total=total)
                chunks = aia_chunker.extract_chunks(local_path, file_type, progress_cb=_progress_cb)

            # 6. Save chunks to DB. Delete any chunks from a previous (failed then
            # retried) attempt first: the whole task body re-runs on retry and
            # create_aia_chunk does not dedupe, so without this a retry would leave
            # duplicate chunk rows polluting vector search. No-op on a first run.
            db.update_aia_source_progress(source_uuid, "chunking")
            db.delete_aia_chunks_by_source(source_id)
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

            # 7. Embed chunks. Batch size = admin-tunable chunks-per-request; each
            # loop pass = one embedding request → fewer hits against the shared
            # GWDG rate limit. Capped by the provider's _BATCH_SIZE ceiling.
            db.update_aia_source_progress(source_uuid, "embedding")
            _t_embed = time.monotonic()
            from src.limits import AIA_EMBEDDING_BATCH_SIZE
            _EMBED_BATCH = int(
                db.get_setting("aia_embedding_batch_size", str(AIA_EMBEDDING_BATCH_SIZE))
            )
            for i in range(0, len(chunks), _EMBED_BATCH):
                batch_chunks = chunks[i: i + _EMBED_BATCH]
                batch_ids = chunk_ids[i: i + _EMBED_BATCH]
                texts = [c["content"] for c in batch_chunks]
                vectors = provider.embed(texts)
                if fingerprint is None and vectors:
                    # dimension for free from the real embedding → no separate probe call
                    fingerprint = fingerprint_from_dim(provider, len(vectors[0]))
                for chunk_id, vector in zip(batch_ids, vectors):
                    db.update_chunk_embedding(chunk_id, vector)
                logger.info(
                    "KI Tutor: embedded chunks {}-{}/{} for source {}",
                    i + 1, i + len(batch_chunks), len(chunks), source_uuid,
                )
            logger.info(
                "KI Tutor: embedding done for {} ({} chunks) in {:.1f}s",
                source_uuid, len(chunks), time.monotonic() - _t_embed,
            )
            # Safety net: chunks existed but no vector came back (shouldn't happen) →
            # probe once so the source still gets a drift fingerprint. Zero-chunk sources
            # keep fingerprint=None (nothing indexed → nothing to drift; stale-check ignores it).
            if fingerprint is None and chunks:
                fingerprint = compute_fingerprint(provider)

        # 7b. Per-source DOC SUMMARY (map-reduce over chunks), built for the not-yet-wired
        # "GENERIC over summaries" Phase 2. CURRENTLY DISABLED via _BUILD_INGEST_SUMMARY:
        # nothing reads aia_sources.summary (verified across chat, backend logic and frontend),
        # so building it only burns map-reduce LLM calls per upload. Code kept intact — flip the
        # flag (top of file) to re-enable when Phase 2 lands. Existing summaries are NOT deleted.
        if _BUILD_INGEST_SUMMARY:
            db.update_aia_source_progress(source_uuid, "summarizing")
            from src.services.aia_summarizer import build_source_summary
            from src.features.ai_assistant.tasks._helpers import _get_llm_client
            from src.limits import AIA_SUMMARY_BATCH_MAX_CHARS
            summary_cap = int(
                db.get_setting("aia_summary_batch_max_chars", str(AIA_SUMMARY_BATCH_MAX_CHARS))
            )
            _t_sum = time.monotonic()
            _sum_client, _sum_model, _ = _get_llm_client()
            summary = build_source_summary(chunks, _sum_client, _sum_model, summary_cap)
            db.update_aia_source_summary(source_uuid, summary)
            logger.info(
                "KI Tutor: summary built for source {} ({} chars) in {:.1f}s",
                source_uuid, len(summary), time.monotonic() - _t_sum,
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

        # 10. Source is ready (chunks embedded + DOC SUMMARY built in step 7b).
        # SPECIFIC answers run on chunk retrieval, GENERIC on the per-source
        # summary (see routes/chat.py). Clear the progress field so the card
        # shows ready.
        db.clear_aia_source_progress(source_uuid)

    except Exception as e:
        from src.services.aia_chunker import PdfNoReadableTextError, OcrFailedError
        from src.i18n import t

        # OcrFailedError has already exhausted its own per-page 429/backoff
        # retries. Do NOT re-run the whole document - mark it failed so the user
        # can re-trigger later via the existing retry button (nothing is lost).
        if not isinstance(e, OcrFailedError):
            # Rate-limit / transient upstream → keep status, requeue task with backoff.
            # Whisper transcription is cached per source_uuid in Redis, so a media
            # retry does not re-transcribe. Chunking + embedding DO re-run from the
            # top; step 6 deletes prior chunks first so a retry never duplicates rows
            # (it does re-embed all batches, bounded by the retry cap).
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
        elif isinstance(e, OcrFailedError):
            error_message = t("ai.source.ocrFailed", locale, page=e.page_number)
        else:
            error_message = str(e)
        db.update_aia_source_status(source_uuid, "failed", error_message=error_message)
        raise
    finally:
        if _aia_job_uuid:
            try:
                from src.features.ai_assistant.scheduling.service import on_complete
                on_complete(_aia_job_uuid)
            except Exception as exc:
                logger.error("KI Tutor: index_source dispatch on_complete failed: {}", exc)


@celery_app.task(bind=True, name="aia.translate_transcript", queue="aia")
def run_translate_transcript(
    self, source_uuid: str, provider_id: int | None = None, target_lang: str | None = None
):
    """Translate a media source's source-language VTT into the workspace target language.

    Runs as a follow-up to indexing so chat is available before translation completes.
    ``provider_id`` is resolved from the ``transcript_translate`` feature route.
    ``target_lang`` falls back to the workspace's ``transcript_target_lang`` (default English).
    """
    try:
        return _run_translate_transcript_inner(source_uuid, provider_id, target_lang)
    except Exception as e:
        msg = str(e).lower()
        is_rate_limit = "429" in msg or "rate limit" in msg
        if is_rate_limit and self.request.retries < 5:
            countdown = min(30 * (2 ** self.request.retries), 120)  # 30s..2m capped
            logger.warning(
                "KI Tutor translate: source {} hit rate limit (attempt {}/{}), retrying in {}s",
                source_uuid, self.request.retries + 1, 5, countdown,
            )
            raise self.retry(exc=e, countdown=countdown, max_retries=5)
        logger.error("KI Tutor translate: source {} failed: {}", source_uuid, e)
        raise


def _resolve_source_vtt(file_path: str, source: dict) -> tuple[str | None, str | None]:
    """Return (vtt_key, source_lang) for a media source's original-language VTT.

    Prefers the Whisper-detected ``language`` on the source; falls back to the
    known target codes for any existing ``_transcript.<code>.vtt`` (older sources
    indexed before the language column was populated).

    One listing instead of a HEAD per candidate language: the bucket is remote,
    so nine probes are nine round trips."""
    from src.i18n import TRANSCRIPT_LANGUAGES

    vorhanden = set(list_keys(aia_transcript_prefix(file_path)))
    source_lang = (source.get("language") or "").lower()
    if source_lang and source_lang != "unknown":
        cand = aia_vtt_key(file_path, source_lang)
        if cand in vorhanden:
            return cand, source_lang
    for code in TRANSCRIPT_LANGUAGES:
        cand = aia_vtt_key(file_path, code)
        if cand in vorhanden:
            return cand, code
    return None, None


def _run_translate_transcript_inner(
    source_uuid: str, provider_id: int | None, target_lang: str | None
) -> None:
    from src.services.subtitle_converter import vtt_to_segments, segments_to_vtt
    from src.storage import get_file, delete_file
    from src.dependencies import get_translate_client_for_provider
    from src.i18n import TRANSCRIPT_LANGUAGES, DEFAULT_TRANSCRIPT_TARGET

    source = db.get_aia_source(source_uuid)
    if source is None:
        logger.warning("KI Tutor translate: source {} not found, skipping", source_uuid)
        return

    file_path = source["file_path"]

    # Target: explicit arg > workspace setting > default English.
    if not target_lang:
        workspace = db.get_aia_workspace_by_id(source["workspace_id"])
        target_lang = (workspace or {}).get("transcript_target_lang") or DEFAULT_TRANSCRIPT_TARGET
    target_lang = target_lang.lower()
    if target_lang not in TRANSCRIPT_LANGUAGES:
        logger.warning("KI Tutor translate: unknown target '{}' for {}, skipping", target_lang, source_uuid)
        return

    source_vtt_key, source_lang = _resolve_source_vtt(file_path, source)
    if not source_vtt_key or not source_lang:
        logger.warning("KI Tutor translate: no source VTT for {}, skipping", source_uuid)
        return

    # Keep exactly the source VTT + the languages in `keep`; drop every other
    # known-language translation so a media source never accumulates spurs.
    def _cleanup_stale(keep: set[str]) -> None:
        vorhanden = set(list_keys(aia_transcript_prefix(file_path)))
        for code in TRANSCRIPT_LANGUAGES:
            if code in keep:
                continue
            stale = aia_vtt_key(file_path, code)
            if stale in vorhanden:
                delete_file(stale)
                logger.info("KI Tutor translate: removed stale {}", stale)

    # Target equals source → nothing to translate; just drop any old translation.
    if target_lang == source_lang:
        _cleanup_stale({source_lang})
        logger.info(
            "KI Tutor translate: target == source ({}) for {}, original kept only",
            source_lang, source_uuid,
        )
        return

    segments = vtt_to_segments(get_file(source_vtt_key).decode("utf-8"))
    if not segments:
        logger.warning("KI Tutor translate: could not parse {}, skipping", source_vtt_key)
        return

    texts = [s["text"] for s in segments]

    client, _glossary = get_translate_client_for_provider(provider_id, feature="transcript_translate")
    if client is None:
        raise RuntimeError(
            "transcript_translate: no translation provider configured — set one in the admin KI panel"
        )

    # DeepLClient expects ISO codes (source "DE", target "EN-US"); LLMTranslationClient
    # uses human-readable names embedded in the prompt ("German", "English").
    from src.services.deepl_client import DeepLClient

    target_meta = TRANSCRIPT_LANGUAGES[target_lang]
    if isinstance(client, DeepLClient):
        translated: list[str] = client.translate_batch(
            texts, source_lang=source_lang.upper(), target_lang=target_meta["deepl"],
        )
    else:
        source_name = TRANSCRIPT_LANGUAGES.get(source_lang, {}).get("name", source_lang)
        translated = client.translate_batch(
            texts, source_lang=source_name, target_lang=target_meta["name"],
        )

    out_segments = [
        {"start": s["start"], "end": s["end"], "text": t_text}
        for s, t_text in zip(segments, translated)
    ]
    target_key = aia_vtt_key(file_path, target_lang)
    _save_transcript_artifact(target_key, segments_to_vtt(out_segments))
    # Overwrite-when-ready: only after the new VTT is saved do we drop the old one,
    # so the player never sees a gap while a re-translation runs.
    _cleanup_stale({source_lang, target_lang})
    logger.info(
        "KI Tutor translate: saved {} ({} segments, {}->{}, provider_id={})",
        target_key, len(out_segments), source_lang, target_lang, provider_id,
    )
