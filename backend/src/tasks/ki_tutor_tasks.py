"""Celery tasks for KI Tutor – indexing source documents."""

import concurrent.futures
import os
import re

from langfuse.decorators import langfuse_context, observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import open_input_file
from src.limits import (
    TUTOR_SUMMARY_MAX_RETRIES,
    TUTOR_SUMMARY_TIMEOUT_SMALL,
    TUTOR_SUMMARY_TIMEOUT_LARGE,
    TUTOR_SUMMARY_MAX_TOKENS_SMALL,
    TUTOR_SUMMARY_MAX_TOKENS_LARGE,
    TUTOR_SUMMARY_MAX_TOKENS_BATCH,
    TUTOR_SUMMARY_CONTENT_MAX_CHARS,
    TUTOR_SUMMARY_PARALLEL_WORKERS_SMALL,
    TUTOR_SUMMARY_PARALLEL_WORKERS_LARGE,
    TUTOR_SUMMARY_BATCH_SIZE,
)
from src.tool_prompts import (
    TUTOR_SUMMARY_PAGE_SYSTEM as _SUMMARY_SYSTEM,
    TUTOR_SUMMARY_PAGE_USER_SMALL as _SUMMARY_USER_SMALL,
    TUTOR_SUMMARY_PAGE_USER_LARGE as _SUMMARY_USER_LARGE,
    TUTOR_SUMMARY_PAGE_BATCH_USER as _SUMMARY_BATCH_USER,
    TUTOR_MINDMAP_PROMPT,
)


def _format_ts(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


def _save_ki_tutor_output(username: str, module_uuid: str, filename: str, data: bytes) -> str:
    """Save a ki-tutor output file (e.g. presentation) in the structured folder."""
    from src.storage import USE_S3
    key = f"ki-tutor/{username}/{module_uuid}/outputs/{filename}"
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    from src.storage import STORAGE_ROOT
    dest = STORAGE_ROOT / "ki-tutor" / username / module_uuid / "outputs"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / filename).write_bytes(data)
    return str(dest / filename)


def _detect_language(text: str) -> str:
    """Simple heuristic language detection based on stop words."""
    german = {"der", "die", "das", "und", "ist", "ein", "eine", "mit", "von", "für", "auf", "des", "den", "auch", "nicht", "sich"}
    english = {"the", "is", "and", "of", "to", "in", "for", "that", "with", "this", "from", "are", "was", "not", "has"}
    words = text.lower().split()[:100]
    de = sum(1 for w in words if w in german)
    en = sum(1 for w in words if w in english)
    return "Deutsch" if de > en else "English"


def _parse_numbered_summaries(text: str, expected_count: int) -> list[str]:
    """Parse '1. summary\\n2. summary\\n...' format.

    Handles multi-line summaries by collecting all text between numbered prefixes.
    """
    # Split into numbered sections: "1. ...", "2. ...", etc.
    parts = re.split(r"(?m)^\s*\d+[\.)]\s*", text.strip())
    # First element is empty (text before first number) — drop it
    parts = [p.strip().replace("\n", " ") for p in parts if p.strip()]
    result = parts[:expected_count]
    while len(result) < expected_count:
        result.append("")
    return result[:expected_count]


def _clean_summary(text: str) -> str:
    """Strip <think> blocks and leading number prefix."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Unclosed <think> — model hit max_tokens while still reasoning
    if "<think>" in text:
        text = text[:text.index("<think>")].strip()
    text = re.sub(r"^\s*\d+[\.)]\s*", "", text).strip()
    return text


def _call_llm_with_retry(client, model, messages, temperature, max_tokens, timeout, extra_body):
    """Make an LLM call with retry on rate limits / timeouts."""
    import time as _time
    for attempt in range(TUTOR_SUMMARY_MAX_RETRIES):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                extra_body=extra_body or None,
            )
        except Exception as e:
            err_str = str(e)
            if ("429" in err_str or "timeout" in err_str.lower()) and attempt < TUTOR_SUMMARY_MAX_RETRIES - 1:
                wait = 30 * (attempt + 1)
                logger.warning(
                    "KI Tutor summaries: rate limit/timeout, retry in {}s ({}/{})",
                    wait, attempt + 1, TUTOR_SUMMARY_MAX_RETRIES,
                )
                _time.sleep(wait)
            else:
                raise


def _summarize_page(client, model, p, is_small, extra_body, lang):
    """Summarize a single page. Returns summary string."""
    sys_msg = _SUMMARY_SYSTEM.format(lang=lang)
    if is_small:
        user_msg = _SUMMARY_USER_SMALL.format(lang=lang, content=p["content"][:TUTOR_SUMMARY_CONTENT_MAX_CHARS])
    else:
        user_msg = _SUMMARY_USER_LARGE.format(lang=lang, content=p["content"][:TUTOR_SUMMARY_CONTENT_MAX_CHARS])

    timeout = TUTOR_SUMMARY_TIMEOUT_SMALL if is_small else TUTOR_SUMMARY_TIMEOUT_LARGE
    max_tokens = TUTOR_SUMMARY_MAX_TOKENS_SMALL if is_small else TUTOR_SUMMARY_MAX_TOKENS_LARGE

    resp = _call_llm_with_retry(
        client, model,
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
        temperature=0.1, max_tokens=max_tokens, timeout=timeout, extra_body=extra_body,
    )
    _msg = resp.choices[0].message
    summary = _clean_summary(_msg.content or getattr(_msg, "reasoning_content", None) or "")
    logger.debug("KI Tutor: page {} summary: {!r}", p["page_number"], summary[:300])
    return summary


def _summarize_batch(client, model, pages_batch, lang):
    """Summarize a batch of pages in one request. Returns list[str] (one per page)."""
    n = len(pages_batch)
    sys_msg = _SUMMARY_SYSTEM.format(lang=lang)
    pages_text = "\n\n".join(
        f"---PAGE {i + 1}---\n{p['content'][:TUTOR_SUMMARY_CONTENT_MAX_CHARS]}"
        for i, p in enumerate(pages_batch)
    )
    user_msg = _SUMMARY_BATCH_USER.format(n=n, lang=lang, pages=pages_text)

    resp = _call_llm_with_retry(
        client, model,
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
        temperature=0.1, max_tokens=TUTOR_SUMMARY_MAX_TOKENS_BATCH,
        timeout=TUTOR_SUMMARY_TIMEOUT_LARGE, extra_body={},
    )
    _msg = resp.choices[0].message
    content = _msg.content or getattr(_msg, "reasoning_content", None) or ""
    # Strip <think> blocks (some models ignore think=False)
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    # Unclosed <think> — keep only what's before it
    if "<think>" in content:
        content = content[:content.index("<think>")].strip()
    summaries = _parse_numbered_summaries(content, n)
    for i, (p, s) in enumerate(zip(pages_batch, summaries)):
        logger.debug("KI Tutor: batch page {} summary: {!r}", p["page_number"], s[:300])
    return summaries


@celery_app.task(bind=True, name="ki_tutor.index_source", queue="ki_tutor")
def run_index_source(self, source_uuid: str):
    try:
        # 1. Load source from DB
        source = db.get_ki_tutor_source(source_uuid)
        if source is None:
            raise RuntimeError(f"Source not found: {source_uuid}")

        source_id = source["id"]
        module_id = source["module_id"]
        file_path_stored = source["file_path"]
        file_type = source["file_type"]
        filename = source["filename"]

        # 2. Status → indexing
        db.update_ki_tutor_source_status(source_uuid, "indexing")
        logger.info("KI Tutor: indexing source {} ({})", source_uuid, filename)

        # 3. Embedding provider + fingerprint
        from src.services.ki_tutor_embeddings import get_embedding_provider, compute_fingerprint
        provider = get_embedding_provider()
        fingerprint = compute_fingerprint(provider)

        from src.config import Settings
        _s = Settings()
        embedding_model = _s.ollama_embedding_model if _s.tutor_embedding_provider == "ollama" else _s.kisski_embedding_model

        # 4. Fetch file from storage
        import os
        suffix = os.path.splitext(filename)[1] or f".{file_type}"
        with open_input_file(file_path_stored, suffix=suffix) as local_path:
            # 5. Extract chunks (branch: media vs document)
            from src.services import ki_tutor_chunker
            media_duration: float | None = None

            if ki_tutor_chunker.is_media_file(file_type):
                # Audio/Video: transcribe with timestamps, then chunk
                from src.services.kisski_client import KisskiClient
                from src.dependencies import _resolve_llm_provider
                _api_key, _base_url, _model, _provider = _resolve_llm_provider()
                if not _api_key:
                    raise RuntimeError("Kein LLM-Provider konfiguriert (für Whisper-Transkription)")
                whisper_client = KisskiClient(
                    api_key=_api_key, base_url=_base_url, model=_model, provider=_provider,
                )
                logger.info("KI Tutor: transcribing media source {} ({})", source_uuid, filename)
                segments, media_duration = whisper_client.transcribe_chunked_verbose(local_path)
                if not segments:
                    raise RuntimeError("Whisper returned no segments for this audio/video file.")
                chunks = ki_tutor_chunker.segments_to_chunks(segments)

                # Save full transcript as .txt next to the source file
                transcript_text = "\n".join(
                    f"[{_format_ts(s['start'])} - {_format_ts(s['end'])}] {s['text']}"
                    for s in segments
                )
                transcript_key = file_path_stored.rsplit(".", 1)[0] + "_transcript.txt"
                from src.storage import USE_S3
                if USE_S3:
                    from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
                    _s3().put_object(Bucket=_S3_BUCKET, Key=transcript_key, Body=transcript_text.encode("utf-8"))
                else:
                    from pathlib import Path as _Path
                    _Path(transcript_key).write_text(transcript_text, encoding="utf-8")
                logger.info("KI Tutor: transcript saved to {}", transcript_key)
            else:
                chunks = ki_tutor_chunker.extract_chunks(local_path, file_type)

            # 6. Save chunks to DB
            chunk_ids: list[int] = []
            for chunk in chunks:
                chunk_id = db.create_ki_tutor_chunk(
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
        db.update_ki_tutor_source_status(
            source_uuid,
            "ready",
            chunk_count=len(chunks),
            embedding_model=embedding_model,
            duration=media_duration,
        )
        logger.info("KI Tutor: source {} indexed ({} chunks)", source_uuid, len(chunks))

        # 9. Check if all non-failed sources for this module are ready → set module ready
        sources = db.get_ki_tutor_sources_by_module(module_id)
        non_failed = [s for s in sources if s["status"] != "failed"]
        all_ready = len(non_failed) > 0 and all(s["status"] == "ready" for s in non_failed)
        if all_ready:
            module = db.get_ki_tutor_module_by_id(module_id)
            if module:
                db.update_ki_tutor_module_status(
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
        db.update_ki_tutor_source_status(source_uuid, "failed", error_message=str(e))
        raise


@celery_app.task(bind=True, name="ki_tutor.generate_summaries", queue="ki_tutor")
@observe(name="ki-tutor-summaries")
def run_generate_summaries(self, source_uuid: str):
    """Generate AI page-level summaries for a PDF source."""
    try:
        source = db.get_ki_tutor_source(source_uuid)
        if source is None:
            raise RuntimeError(f"Source not found: {source_uuid}")

        if source["file_type"] != "pdf":
            return

        db.update_ki_tutor_source_summaries_status(source_uuid, "generating")
        logger.info("KI Tutor: generating page summaries for source {}", source_uuid)

        # 1. Extract text per page
        import os
        suffix = os.path.splitext(source["filename"])[1] or ".pdf"
        with open_input_file(source["file_path"], suffix=suffix) as local_path:
            from src.services.ki_tutor_chunker import extract_page_texts
            pages = extract_page_texts(local_path)

        if not pages:
            db.update_ki_tutor_source_summaries_status(source_uuid, "ready")
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
            db.update_ki_tutor_source_summaries_status(source_uuid, "ready")
            logger.info("KI Tutor: all pages already summarized for {}", source_uuid)
            return

        logger.info(
            "KI Tutor: {} of {} pages need summaries for {}",
            len(remaining_pages), len(pages), source_uuid,
        )

        # 5. Generate summaries — save each batch/page immediately to DB
        #    Small models (ollama): parallel single-page requests
        #    Large models (cloud):  parallel batches of TUTOR_SUMMARY_BATCH_SIZE pages
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
            with concurrent.futures.ThreadPoolExecutor(max_workers=TUTOR_SUMMARY_PARALLEL_WORKERS_SMALL) as executor:
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
            batches = [remaining_pages[i:i + TUTOR_SUMMARY_BATCH_SIZE] for i in range(0, len(remaining_pages), TUTOR_SUMMARY_BATCH_SIZE)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=TUTOR_SUMMARY_PARALLEL_WORKERS_LARGE) as executor:
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
            db.update_ki_tutor_source_summaries_status(source_uuid, "failed")
            logger.warning(
                "KI Tutor: {} batch(es) failed for {} — saved partial results, retry will resume",
                failed_batches, source_uuid,
            )
        else:
            db.update_ki_tutor_source_summaries_status(source_uuid, "ready")
            logger.info("KI Tutor: page summaries ready for source {} ({} pages)", source_uuid, len(pages))

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "rate" in err_str.lower():
            status = "rate_limited"
        else:
            status = "failed"
        logger.error("KI Tutor: summary generation {} for {}: {}", status, source_uuid, e)
        db.update_ki_tutor_source_summaries_status(source_uuid, status)


@celery_app.task(bind=True, name="ki_tutor.generate_mindmap", queue="ki_tutor",
                 soft_time_limit=300, time_limit=360)
@observe(name="ki-tutor-mindmap")
def run_generate_mindmap(self, mindmap_id: int, source_ids: list[int], source_uuids: list[str]):
    """Generate a mindmap from source summaries as a background job."""
    import json as _json

    try:
        db.update_ki_tutor_mindmap(mindmap_id, "running")
        logger.info("KI Tutor: generating mindmap {}", mindmap_id)

        # 1. Build context from page summaries (with fallback to chunks)
        from pathlib import Path as _Path
        _MEDIA_EXTS = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac", ".aac"}

        def _fmt_time(seconds: float) -> str:
            s = int(seconds)
            h, s = divmod(s, 3600)
            m, s = divmod(s, 60)
            return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

        context_parts: list[str] = []
        for sid, suuid in zip(source_ids, source_uuids):
            source = db.get_ki_tutor_source(suuid)
            source_label = source["filename"] if source else "Quelle"
            is_media = _Path(source_label).suffix.lower() in _MEDIA_EXTS if source else False

            if is_media:
                # For media: use chunks with start_time as label
                chunks = db.get_chunks_by_source(sid)
                if chunks:
                    parts = []
                    for c in chunks[:20]:
                        st = c.get("start_time")
                        time_label = _fmt_time(st) if st is not None else f"Teil {c['page_number']}"
                        parts.append(f"[{source_label}, {time_label}] {c['content']}")
                    context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))
            else:
                summaries = db.get_paragraph_summaries_by_source(sid)
                if summaries:
                    pages: dict[int, list[str]] = {}
                    for s in summaries:
                        pages.setdefault(s["page_number"], []).append(s["summary"])
                    parts = [f"[{source_label}, S. {p}] {' '.join(texts)}" for p, texts in sorted(pages.items())]
                    context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))
                else:
                    chunks = db.get_chunks_by_source(sid)
                    if chunks:
                        parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks[:20]]
                        context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))

        if not context_parts:
            db.update_ki_tutor_mindmap(mindmap_id, "failed", error="Keine Inhalte vorhanden")
            return

        # Fair budget split per source (200k total, whole summaries only)
        budget_per_source = 200000 // len(source_ids)
        trimmed_parts: list[str] = []
        for part in context_parts:
            lines = part.split("\n")
            header = lines[0]  # "--- Dateiname ---"
            kept = [header]
            size = len(header)
            for line in lines[1:]:
                if size + len(line) + 1 > budget_per_source:
                    break
                kept.append(line)
                size += len(line) + 1
            trimmed_parts.append("\n".join(kept))
        context = "\n\n".join(trimmed_parts)

        # 2. Call LLM
        from langfuse.openai import OpenAI
        from src.dependencies import _resolve_llm_provider
        _api_key, _base_url, _model, _provider = _resolve_llm_provider()
        client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=240)
        model = _model
        langfuse_context.update_current_observation(
            metadata={"provider": _provider, "base_url": _base_url, "model": model},
        )

        messages = [
            {"role": "system", "content": TUTOR_MINDMAP_PROMPT},
            {"role": "user", "content": f"/no_think\nErstelle eine Mindmap aus folgenden Quellen:\n\n{context}"},
        ]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
        )

        msg = response.choices[0].message
        raw = msg.content or getattr(msg, "reasoning_content", None)
        if not raw:
            db.update_ki_tutor_mindmap(mindmap_id, "failed", error="LLM returned empty content")
            return

        answer = raw.strip()
        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        # Strip leading thinking tags if model wrapped output
        if answer.startswith("<think>"):
            think_end = answer.find("</think>")
            if think_end != -1:
                answer = answer[think_end + 8:].strip()

        mindmap = _json.loads(answer)
        if not isinstance(mindmap, dict) or "topic" not in mindmap:
            db.update_ki_tutor_mindmap(mindmap_id, "failed", error="Invalid mindmap format")
            return

        db.update_ki_tutor_mindmap(mindmap_id, "success", mindmap=mindmap)
        logger.info("KI Tutor: mindmap {} generated successfully", mindmap_id)

    except Exception as e:
        logger.error("KI Tutor: mindmap {} generation failed: {}", mindmap_id, e)
        db.update_ki_tutor_mindmap(mindmap_id, "failed", error=str(e))


# ─── Presentation generation (NotebookLM-style + FLUX images) ───────────────

# NotebookLM-inspired slide prompt — clean, statement-driven, icon-aware layouts
_PRES_PROMPT = (
    "Du erstellst eine professionelle Präsentation im Stil von Google NotebookLM: clean, modern, viel Whitespace, "
    "große fette Aussagesätze als Titel (KEINE generischen Titel wie 'Überblick' — stattdessen 'Warum dieses Projekt den Unterschied macht.').\n\n"
    "Antworte NUR mit JSON:\n"
    "{\n"
    '  "title": "Präsentationstitel",\n'
    '  "slides": [\n'
    '    {"layout": "deckblatt", "title": "Große Aussage als Titel", "subtitle": "Ergänzender Untertitel", "image_prompt": "..."},\n'
    '    {"layout": "kapitel", "number": "1", "title": "Abschnittstitel", "subtitle": "Kurzbeschreibung"},\n'
    '    {"layout": "statement", "title": "Eine starke Aussage als ganzer Satz.", "body": "2-3 Sätze Erklärung dazu."},\n'
    '    {"layout": "content", "title": "Aussage als Titel.", "bullets": ["Punkt 1", "Punkt 2", "Punkt 3"], "image_prompt": "..."},\n'
    '    {"layout": "icon_grid", "title": "Vier Vorteile auf einen Blick.", "items": [\n'
    '      {"title": "Punkt A", "body": "Kurze Erklärung in 1-2 Sätzen."},\n'
    '      {"title": "Punkt B", "body": "Kurze Erklärung."},\n'
    '      {"title": "Punkt C", "body": "Kurze Erklärung."},\n'
    '      {"title": "Punkt D", "body": "Kurze Erklärung."}\n'
    '    ]},\n'
    '    {"layout": "vergleich", "title": "Vergleich als Aussage.", "left_title": "Option A", "left_bullets": ["..."], "right_title": "Option B", "right_bullets": ["..."]},\n'
    '    {"layout": "zitat", "title": "Kontextüberschrift", "quote": "Zitattext oder Kernaussage.", "body": "Erklärung dazu."},\n'
    '    {"layout": "zweispalten", "title": "Gegenüberstellung.", "left_bullets": ["Links 1", "Links 2"], "right_bullets": ["Rechts 1", "Rechts 2"]},\n'
    '    {"layout": "statistik", "title": "Die Zahlen sprechen für sich.", "stats": [{"value": "42%", "label": "Label", "description": "Beschreibung"}]},\n'
    '    {"layout": "zeitstrahl", "title": "In drei Schritten zum Ziel.", "steps": [{"label": "Schritt 1", "description": "Beschreibung"}]},\n'
    '    {"layout": "zusammenfassung", "title": "Kernbotschaft.", "bullets": ["Fazit 1", "Fazit 2", "Fazit 3"]},\n'
    '    {"layout": "abschluss", "title": "Vielen Dank.", "subtitle": "Kontaktinfo oder Schlusswort"}\n'
    "  ]\n"
    "}\n\n"
    "Layouts (12 verfügbar):\n"
    "- deckblatt: Titelfolie (1x am Anfang). image_prompt = englischer Prompt für Illustration.\n"
    "- kapitel: Abschnittstrenner mit großer Zahl (1, 2, 3...) + Titel + Beschreibung. Dunkler Hintergrund.\n"
    "- content: Aussage-Titel + 3-5 Bullet Points (max 12 Wörter/Punkt) + optional image_prompt.\n"
    "- statement: Große fette Aussage + Fließtext. Kein Bild, keine Bullets.\n"
    "- icon_grid: 2x2 Raster mit 4 Punkten (je title + body). Für Vorteile, Features, Übersichten.\n"
    "- vergleich: Zwei Boxen nebeneinander mit Titel + Bullets pro Seite.\n"
    "- zitat: Hervorgehobenes Zitat/Kernaussage in Box + erklärende Beschreibung.\n"
    "- zweispalten: Zwei Spalten nebeneinander mit left_bullets/right_bullets.\n"
    "- statistik: Große Zahlen/Statistiken (bis 3 stats mit value + label + description).\n"
    "- zeitstrahl: Nummerierte Schritte/Prozess (steps mit label + description, max 6).\n"
    "- zusammenfassung: Vorletzte Folie mit Kernaussagen als Bullets.\n"
    "- abschluss: Letzte Folie (1x am Ende) mit Schlussbotschaft (title + subtitle).\n\n"
    "Regeln:\n"
    "- {slide_count} Folien (inkl. Deckblatt + Abschluss)\n"
    "- Titel sind IMMER vollständige Aussagesätze mit Punkt am Ende.\n"
    "- Mische die Layouts — NICHT nur 'content' Folien!\n"
    "- STICHPUNKTE statt Fließtext — max 6-8 Wörter pro Bullet. Keine ganzen Sätze in Bullets.\n"
    "- Max 5-6 Bullets pro Content-Folie. Lieber eine Folie mehr als zu viele Punkte.\n"
    "- Verwende kapitel-Folien um größere Abschnitte zu markieren.\n"
    "- icon_grid für Übersichten mit 4 gleichwertigen Punkten.\n"
    "- statement für einzelne starke Aussagen.\n"
    "- zitat für wichtige Zitate oder Kernbotschaften.\n"
    "- statistik wenn es harte Zahlen/Daten gibt.\n"
    "- zeitstrahl für Prozesse, Abläufe, Schritte.\n"
    "- zweispalten für Gegenüberstellungen oder parallele Informationen.\n"
    "- Erste Folie IMMER 'deckblatt', letzte IMMER 'abschluss'.\n"
    "- image_prompt: Nur bei deckblatt und content. Englisch. Stil: 'flat vector illustration, people in modern setting, warm muted colors, white background, no text'. Max 3 Bilder total.\n"
    "- Texte EXAKT aus der Quelle — keine Umformulierungen, keine Rechtschreibfehler.\n"
    "- Sprache = Sprache der Quelle.\n"
    "- Antworte NUR mit JSON."
)



# ── Shared helpers for exercise / datentabelle / glossary generation ─────────

def _get_llm_client():
    """Return (client, model, provider) using the configured LLM provider."""
    from langfuse.openai import OpenAI
    from src.dependencies import _resolve_llm_provider
    _api_key, _base_url, _model, _provider = _resolve_llm_provider()
    client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=120)
    langfuse_context.update_current_observation(
        metadata={"provider": _provider, "base_url": _base_url, "model": _model},
    )
    return client, _model, _provider


def _clean_llm_json(text: str) -> str:
    """Strip markdown fences and leading/trailing whitespace from LLM JSON output."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


# ── Datentabelle generation ──────────────────────────────────────────────────


@celery_app.task(bind=True, name="ki_tutor.generate_datentabelle", queue="ki_tutor",
                 soft_time_limit=120, time_limit=180)
@observe(name="ki-tutor-datentabelle")
def run_generate_datentabelle(self, datentabelle_id: int, source_ids: list[int],
                              source_uuids: list[str], source_map: dict):
    """Generate a data table from source chunks as a background job."""
    import json as _json
    from src.tool_prompts import TUTOR_DATENTABELLE_PROMPT

    try:
        db.update_ki_tutor_datentabelle(datentabelle_id, "running")
        logger.info("KI Tutor: generating datentabelle {}", datentabelle_id)

        # Build context with source filenames for citations
        _MEDIA_EXTS = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac", ".aac"}
        context_parts: list[str] = []
        context_len = 0
        for sid, suuid in zip(source_ids, source_uuids):
            chunks = db.get_chunks_by_source(sid)
            src_info = source_map.get(str(sid), {})
            filename = src_info.get("filename", f"Quelle {src_info.get('number', '?')}")
            is_media = any(filename.lower().endswith(ext) for ext in _MEDIA_EXTS)
            for chunk in chunks:
                if is_media and chunk.get("start_time") is not None:
                    st = chunk["start_time"]
                    h, m, s = int(st // 3600), int((st % 3600) // 60), int(st % 60)
                    ts = f"{h}:{m:02}:{s:02}" if h > 0 else f"{m}:{s:02}"
                    part = f"[{filename}, {ts}]\n{chunk['content']}"
                else:
                    part = f"[{filename}, S. {chunk['page_number']}]\n{chunk['content']}"
                if context_len + len(part) > 200000:
                    break
                context_parts.append(part)
                context_len += len(part)

        if not context_parts:
            db.update_ki_tutor_datentabelle(datentabelle_id, "failed", error="Keine Chunks vorhanden")
            return

        context = "\n\n---\n\n".join(context_parts)

        client, model, _ = _get_llm_client()
        messages = [
            {"role": "system", "content": TUTOR_DATENTABELLE_PROMPT},
            {"role": "user", "content": (
                f"Erstelle eine strukturierte Datentabelle aus folgendem Text:\n\n{context}"
            )},
        ]

        response = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
        raw = response.choices[0].message.content
        if not raw:
            db.update_ki_tutor_datentabelle(datentabelle_id, "failed", error="LLM returned empty content")
            return

        table_data = _json.loads(_clean_llm_json(raw))
        if not isinstance(table_data, dict) or "columns" not in table_data or "rows" not in table_data:
            db.update_ki_tutor_datentabelle(datentabelle_id, "failed", error="Invalid table format")
            return

        sources_list = [
            {"number": info["number"], "filename": info["filename"]}
            for info in sorted(source_map.values(), key=lambda x: x["number"])
        ]
        title = table_data.get("title", "Datentabelle")

        db.update_ki_tutor_datentabelle(datentabelle_id, "success",
                                        title=title, table_data=table_data, sources=sources_list)
        logger.info("KI Tutor: datentabelle {} generated successfully", datentabelle_id)

    except Exception as e:
        logger.error("KI Tutor: datentabelle {} generation failed: {}", datentabelle_id, e)
        db.update_ki_tutor_datentabelle(datentabelle_id, "failed", error=str(e))


# ── Glossary generation ──────────────────────────────────────────────────────

_GLOSSARY_PROMPT = """Du bist ein Fachsprachen-Experte. Extrahiere die wichtigsten Fachbegriffe aus dem folgenden Text.

Die Textausschnitte sind mit Quellenangaben markiert: [Q1, S. 5] = Quelle 1, Seite 5.

Für jeden Begriff gib EXAKT dieses JSON-Format zurück (als JSON-Array):
[
  {
    "term_de": "Fachbegriff in der Quellsprache",
    "term_en": "Übersetzung (siehe Regeln)",
    "definition": "Kurze Erklärung auf Deutsch (B1 Niveau, 1-2 Sätze)",
    "definition_en": "Short explanation in English (B1 level, 1-2 sentences)",
    "example_sentence": "Ein Satz aus dem Text, der den Begriff verwendet",
    "example_sentence_en": "English translation of the example sentence",
    "source_label": "Q1",
    "page_number": 5
  }
]

Regeln:
- Extrahiere 10-20 Fachbegriffe (die wichtigsten und häufigsten)
- Nur echte Fachbegriffe, keine allgemeinen Wörter
- KRITISCH für term_de: Der Begriff muss WÖRTLICH als zusammenhängendes Wort oder Phrase im Text vorkommen. Wenn der Text "in den deutschen Arbeitsmarkt zu integrieren" sagt, darfst du NICHT "Arbeitsmarktintegration" daraus machen. Nimm stattdessen "Arbeitsmarkt" oder lass es weg. Erfinde KEINE Komposita oder Nominalisierungen die nicht exakt so im Text stehen.
- term_en: Wenn der Quelltext NICHT auf Englisch ist, übersetze den Begriff ins Englische. Wenn der Quelltext auf Englisch ist, übersetze den Begriff ins Deutsche. Niemals die gleiche Sprache wie term_de verwenden!
- definition: Einfache Erklärung auf Deutsch, verständlich auf B1-Sprachniveau
- definition_en: Einfache Erklärung auf Englisch, verständlich auf B1-Sprachniveau
- example_sentence: Ein Satz aus dem gegebenen Text, der den Begriff verwendet
- example_sentence_en: Englische Übersetzung dieses Satzes
- source_label: Die Quellenangabe (Q1, Q2, ...) aus der der Begriff stammt
- page_number ist die Seitenzahl, auf der der Begriff vorkommt
- Antworte NUR mit dem JSON-Array, kein anderer Text"""


@celery_app.task(bind=True, name="ki_tutor.generate_glossary", queue="ki_tutor",
                 soft_time_limit=120, time_limit=180)
@observe(name="ki-tutor-glossary")
def run_generate_glossary(self, module_id: int, source_ids: list[int]):
    """Generate glossary entries from source chunks as a background job."""
    import json as _json

    try:
        logger.info("KI Tutor: generating glossary for module {} sources {}", module_id, source_ids)

        # Gather chunks from all selected sources, track which source each chunk belongs to
        all_chunks: list[dict] = []
        for sid in source_ids:
            chunks = db.get_chunks_by_source(sid)
            for c in chunks:
                c["_source_id"] = sid
            all_chunks.extend(chunks)
        if not all_chunks:
            logger.warning("KI Tutor: glossary generation — no chunks found")
            return

        # Build source label map: source_id → "Q1", "Q2", ...
        sid_to_label: dict[int, str] = {}
        label_to_sid: dict[str, int] = {}
        for i, sid in enumerate(source_ids, 1):
            label = f"Q{i}"
            sid_to_label[sid] = label
            label_to_sid[label] = sid

        # Build context (max ~200000 chars) with source labels
        context_parts: list[str] = []
        context_len = 0
        for chunk in all_chunks:
            label = sid_to_label.get(chunk["_source_id"], "Q1")
            part = f"[{label}, S. {chunk['page_number']}]\n{chunk['content']}"
            if context_len + len(part) > 200000:
                break
            context_parts.append(part)
            context_len += len(part)
        context = "\n\n---\n\n".join(context_parts)

        # Tell LLM which terms already exist so it doesn't repeat them
        existing = db.get_ki_tutor_glossary_by_module(module_id)
        existing_terms_list = [e["term_de"] for e in existing]
        exclude_hint = ""
        if existing_terms_list:
            exclude_hint = f"\n\nFolgende Begriffe existieren bereits — überspringe diese: {', '.join(existing_terms_list)}"

        client, model, _ = _get_llm_client()
        messages = [
            {"role": "system", "content": _GLOSSARY_PROMPT},
            {"role": "user", "content": f"Extrahiere Fachbegriffe aus folgendem Text:\n\n{context}{exclude_hint}"},
        ]

        response = client.chat.completions.create(model=model, messages=messages, temperature=0.1)
        raw = response.choices[0].message.content
        if not raw:
            logger.error("KI Tutor: glossary generation — LLM returned empty content")
            return

        entries_raw = _json.loads(_clean_llm_json(raw))
        if not isinstance(entries_raw, list):
            logger.error("KI Tutor: glossary generation — expected JSON array")
            return

        # Validate: term must appear verbatim in source text
        context_lower = context.lower()
        entries_raw = [e for e in entries_raw if e.get("term_de", "").strip().lower() in context_lower]

        # Deduplicate: skip terms that already exist
        existing = db.get_ki_tutor_glossary_by_module(module_id)
        existing_terms = {e["term_de"].strip().lower() for e in existing}
        new_entries = [e for e in entries_raw if e.get("term_de", "").strip().lower() not in existing_terms]

        # Respect limit of 150
        remaining_slots = 150 - len(existing)
        if remaining_slots <= 0:
            logger.info("KI Tutor: glossary limit reached for module {}, skipping", module_id)
            return
        new_entries = new_entries[:remaining_slots]

        if new_entries:
            # Group entries by source_id based on LLM's source_label
            from collections import defaultdict
            entries_by_source: dict[int, list[dict]] = defaultdict(list)
            for entry in new_entries:
                lbl = entry.pop("source_label", "Q1")
                sid = label_to_sid.get(lbl, source_ids[0])
                entries_by_source[sid].append(entry)
            for sid, entries in entries_by_source.items():
                db.bulk_create_glossary_entries(sid, entries)
        logger.info("KI Tutor: glossary added {} new entries (skipped {} duplicates) for module {}",
                     len(new_entries), len(entries_raw) - len(new_entries), module_id)

    except Exception as e:
        logger.error("KI Tutor: glossary generation failed for module {}: {}", module_id, e)


# ── Exercise Set generation (replaces threading.Thread) ──────────────────────


@celery_app.task(bind=True, name="ki_tutor.generate_exercise_set", queue="ki_tutor",
                 soft_time_limit=120, time_limit=180)
@observe(name="ki-tutor-exercise-set")
def run_generate_exercise_set(self, set_id: int, module_id: int, tool: str,
                              mode: str, count: int, source_uuid: str | None = None,
                              source_uuids: list[str] | None = None):
    """Generate items for an exercise set (lernkarten/lueckentext/vokabeltest)."""
    import json as _json
    import random
    from src.tool_prompts import TUTOR_LERNKARTEN_PROMPT, TUTOR_KARTEIKARTEN_PROMPT

    try:
        module = db.get_ki_tutor_module_by_id(module_id)
        if not module:
            db.fail_exercise_set(set_id)
            return

        items = []
        title = "Wird generiert…"
        client, model, _ = _get_llm_client()

        if mode == "glossar":
            glossary = db.get_ki_tutor_glossary_by_module(module_id)
            if not glossary:
                db.fail_exercise_set(set_id)
                return
            selected = random.sample(glossary, min(count, len(glossary)))

            if tool == "lernkarten":
                items = [
                    {"front": e["term_de"],
                     "back": f"{e['term_de']} — {e['definition']}",
                     "back_en": f"{e['term_en']}",
                     "source_label": e.get("filename", ""), "page_number": e.get("page_number")}
                    for e in selected
                ]
            elif tool == "karteikarten":
                items = [
                    {"front": e["term_de"], "back": f"{e['term_en']} — {e['definition']}",
                     "source_label": e.get("filename", ""), "page_number": e.get("page_number")}
                    for e in selected
                ]
            elif tool == "lueckentext":
                terms_text = "\n".join(f"- {e['term_de']} ({e['term_en']}): {e['definition']}" for e in selected)
                messages = [
                    {"role": "system", "content": (
                        "Du erstellst Lückentext-Übungen. Für jeden Begriff erstelle einen Satz "
                        "mit einer Lücke, die durch den Begriff gefüllt werden muss.\n\n"
                        "Antworte NUR mit einem JSON-Array:\n"
                        '[{"sentence": "Der Prozess der ___ reduziert Redundanz.", '
                        '"answer": "Normalisierung", '
                        '"options": ["Indexierung", "Normalisierung", "Partitionierung", "Denormalisierung"], '
                        '"correct_idx": 1, "term_de": "Normalisierung", "page_number": 12}]\n\n'
                        "Regeln:\n- Genau 4 Optionen pro Frage, eine davon korrekt\n"
                        "- correct_idx = Index der richtigen Option (0-3)\n"
                        "- ___ als Lücken-Platzhalter\n"
                        "- Verwende KEINE Personennamen in Fragen. Statt 'laut Prof. X' schreibe 'laut Quelle'\n"
                        "- Antworte NUR mit dem JSON-Array"
                    )},
                    {"role": "user", "content": f"Erstelle Lückentext-Übungen:\n\n{terms_text}"},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                exercises = _json.loads(answer)[:count]
                items = [
                    {"front": ex["sentence"], "back": ex["answer"], "options": ex["options"],
                     "correct_idx": ex["correct_idx"],
                     "source_label": next((e.get("filename", "") for e in selected if e["term_de"] == ex.get("term_de")), ""),
                     "page_number": ex.get("page_number")}
                    for ex in exercises
                ]
            elif tool == "vokabeltest":
                terms_text = "\n".join(f"- {e['term_de']} ({e['term_en']}): {e['definition']}" for e in selected)
                messages = [
                    {"role": "system", "content": (
                        "Du erstellst ein Begriffe-Quiz zu Fachbegriffen (Multiple Choice).\n\n"
                        "Antworte NUR mit einem JSON-Array:\n"
                        '[{"question": "Was ist die englische Übersetzung von Normalisierung?", '
                        '"options": ["Indexing", "Normalization", "Partitioning", "Denormalization"], '
                        '"correct_idx": 1, "explanation": "Normalization ist...", '
                        '"term_de": "Normalisierung"}]\n\n'
                        "Regeln:\n- Mische DE→EN, EN→DE, Definitionsfragen\n"
                        "- Wähle Begriffe die sich gut für MC eignen (klare Definition, plausible Distraktoren)\n"
                        "- Genau 4 Optionen, eine korrekt\n- correct_idx = 0-3\n"
                        "- Verwende KEINE Personennamen in Fragen. Statt 'laut Prof. X' schreibe 'laut Quelle'\n"
                        "- Antworte NUR mit dem JSON-Array"
                    )},
                    {"role": "user", "content": f"Erstelle Begriffe-Quiz-Fragen zu diesen Fachbegriffen:\n\n{terms_text}"},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                questions = _json.loads(answer)[:count]
                items = [
                    {"front": q["question"], "back": q["options"][q["correct_idx"]], "options": q["options"],
                     "correct_idx": q["correct_idx"], "explanation": q.get("explanation"),
                     "source_label": next((e.get("filename", "") for e in selected if e["term_de"] == q.get("term_de")), ""),
                     "page_number": q.get("page_number")}
                    for q in questions
                ]

            # Generate a short title via LLM from glossary terms
            terms_summary = ", ".join(e["term_de"] for e in selected)
            try:
                title_resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "Gib einen kurzen, prägnanten Titel der das Thema dieser Fachbegriffe zusammenfasst. Antworte NUR mit dem Titel, ohne Anführungszeichen."},
                        {"role": "user", "content": terms_summary},
                    ],
                    temperature=0.3,
                    max_tokens=80,
                )
                title = (title_resp.choices[0].message.content or "").strip().strip('"\'')
                if not title:
                    title = ", ".join(e["term_de"] for e in selected)
            except Exception:
                title = ", ".join(e["term_de"] for e in selected)

        elif mode == "quelle":
            # Support multi-source: prefer source_uuids list, fall back to single source_uuid
            uuids = source_uuids or ([source_uuid] if source_uuid else [])
            if not uuids:
                db.fail_exercise_set(set_id)
                return

            # Build context from all sources
            context_parts: list[str] = []
            first_label = ""
            # Mapping: (source_label, page_number) → start_time for media files
            _time_map: dict[tuple[str, int], float] = {}
            # Mapping: filename → source dict (for chunk lookup in lernkarten)
            _source_by_name: dict[str, dict] = {}
            for suuid in uuids:
                source = db.get_ki_tutor_source(suuid)
                if not source:
                    continue
                source_label = source["filename"]
                _source_by_name[source_label] = source
                if not first_label:
                    first_label = source_label
                # For karteikarten: use raw chunks so LLM can quote verbatim for evidence validation
                # For other tools: use summaries (faster, denser)
                use_chunks = tool == "karteikarten"
                chunks_all = db.get_chunks_by_source(source["id"]) if use_chunks else None
                summaries = None if use_chunks else db.get_paragraph_summaries_by_source(source["id"])
                if use_chunks and chunks_all:
                    for c in chunks_all:
                        if c.get("start_time") is not None:
                            _time_map[(source_label, c["page_number"])] = c["start_time"]
                    parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks_all]
                    context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))
                elif summaries:
                    pages_map: dict[int, list[str]] = {}
                    for s in summaries:
                        pages_map.setdefault(s["page_number"], []).append(s["summary"])
                    parts = [f"[{source_label}, S. {p}] {' '.join(texts)}" for p, texts in sorted(pages_map.items())]
                    context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))
                else:
                    chunks = db.get_chunks_by_source(source["id"])
                    if chunks:
                        for c in chunks:
                            if c.get("start_time") is not None:
                                _time_map[(source_label, c["page_number"])] = c["start_time"]
                        parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks[:30]]
                        context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))

            if not context_parts:
                db.fail_exercise_set(set_id)
                return

            # Fair budget split per source (200k total, whole lines only)
            budget_per_source = 200000 // len(context_parts)
            trimmed: list[str] = []
            for part in context_parts:
                lines = part.split("\n")
                header = lines[0]
                kept = [header]
                size = len(header)
                for line in lines[1:]:
                    if size + len(line) + 1 > budget_per_source:
                        break
                    kept.append(line)
                    size += len(line) + 1
                trimmed.append("\n".join(kept))
            context = "\n\n".join(trimmed)
            multi_label = first_label if len(uuids) == 1 else f"{len(uuids)} Quellen"
            source_hint = "folgender Quelle" if len(uuids) == 1 else "folgenden Quellen"

            import re as _re_card

            def _normalize_chunk(text: str) -> str:
                text = _re_card.sub(r"-\s*\n\s*", "", text)
                text = _re_card.sub(r"\s*\n\s*", " ", text)
                return text.strip()

            def _find_all_pages(search_term: str) -> list[dict]:
                """Find all pages where search_term appears in chunk text."""
                term_lower = search_term.lower()
                if not term_lower:
                    return []
                seen: set[tuple[str, int]] = set()
                result: list[dict] = []
                for sname, src in _source_by_name.items():
                    for ch in db.get_chunks_by_source(src["id"]):
                        key = (sname, ch["page_number"])
                        if key in seen:
                            continue
                        if term_lower in _normalize_chunk(ch["content"]).lower():
                            seen.add(key)
                            result.append({
                                "source_label": sname,
                                "page_number": ch["page_number"],
                                "start_time": _time_map.get(key),
                            })
                # Sort: by filename, then by start_time (media) or page_number
                result.sort(key=lambda s: (
                    s.get("source_label", ""),
                    s.get("start_time") if s.get("start_time") is not None else (s.get("page_number") or 0),
                ))
                return result

            def _parse_card(c: dict, include_back_en: bool = False, search_term: str = "", multi_source: bool = False) -> dict:
                """Parse card. search_term validates/corrects page. multi_source=True stores all pages."""
                sl = c.get("source_label", first_label)
                pn = c.get("page_number")
                item: dict = {
                    "front": c["front"], "back": c["back"],
                    "source_label": sl,
                    "page_number": pn,
                    "start_time": _time_map.get((sl, pn or 0)),
                }
                if include_back_en:
                    item["back_en"] = c.get("back_en", "")
                if search_term:
                    pages = _find_all_pages(search_term)
                    if pages:
                        if multi_source:
                            item["sources"] = pages
                        # Keep LLM-assigned page if it contains the term, otherwise use first match
                        llm_page_valid = any(
                            p["source_label"] == sl and p["page_number"] == pn
                            for p in pages
                        )
                        if not llm_page_valid:
                            item["source_label"] = pages[0]["source_label"]
                            item["page_number"] = pages[0]["page_number"]
                            item["start_time"] = pages[0].get("start_time")
                return item

            if tool == "lernkarten":
                prompt = TUTOR_LERNKARTEN_PROMPT.replace("{count}", str(count))
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Erstelle Lernkarten aus {source_hint}:\n\n{context}"},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                data = _json.loads(answer)

                def _format_lernkarte(c: dict) -> dict:
                    """Format lernkarte with word parts, example sentence, etc."""
                    item = _parse_card(c, include_back_en=True, search_term=c.get("front", ""), multi_source=True)
                    # Build structured back text from new fields
                    parts = [c.get("back", "").strip()]
                    wp = c.get("word_parts", "").strip()
                    wpe = c.get("word_parts_explained", "").strip()
                    if wp:
                        parts.append(f"\n**Wortzerlegung**\n{wp}")
                        if wpe:
                            parts.append(wpe)
                    # Use LLM-generated example sentence (simple B1-level usage example)
                    ex = c.get("example_sentence", "").strip()
                    if ex:
                        parts.append(f"\n**Beispiel:**\n*\u201E{ex}\u201C*")

                    item["back"] = "\n".join(parts)
                    return item
                items = [_format_lernkarte(c) for c in data.get("cards", [])][:count]
                title = data.get("title", multi_label)
            elif tool == "karteikarten":
                prompt = TUTOR_KARTEIKARTEN_PROMPT.replace("{count}", str(count))
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Erstelle Karteikarten aus {source_hint}:\n\n{context}"},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                data = _json.loads(answer)
                def _normalize_for_match(text: str) -> str:
                    """Normalize text for fuzzy substring matching (whitespace, punctuation, case)."""
                    text = _normalize_chunk(text).lower()
                    text = _re_card.sub(r"[^\w\säöüß]+", " ", text)
                    text = _re_card.sub(r"\s+", " ", text)
                    return text.strip()

                def _evidence_matches_page(evidence_norm: str, page_text_norm: str) -> bool:
                    """Check if evidence is fully or partially (6+ consecutive words) contained in page."""
                    if not evidence_norm or not page_text_norm:
                        return False
                    if evidence_norm in page_text_norm:
                        return True
                    ev_words = evidence_norm.split()
                    if len(ev_words) < 6:
                        return False
                    for window in range(min(len(ev_words), 20), 5, -1):
                        for i in range(len(ev_words) - window + 1):
                            phrase = " ".join(ev_words[i:i + window])
                            if phrase in page_text_norm:
                                return True
                    return False

                def _parse_karteikarte(c: dict) -> dict:
                    # Build back text from answer_parts statements
                    answer_parts = c.get("answer_parts") or []
                    back_text = " ".join((p.get("statement") or "").strip() for p in answer_parts if p.get("statement"))
                    c_merged = dict(c)
                    c_merged["back"] = back_text or c.get("back", "")
                    item = _parse_card(c_merged)

                    # Enforce single source per karteikarte
                    sl = c.get("source_label") or first_label
                    src_obj = _source_by_name.get(sl)
                    if not src_obj:
                        return item

                    # Build original page_text lookup (deduped for overlapping chunks)
                    def _build_page_text(chunks: list) -> str:
                        """Concatenate chunks, removing overlap between consecutive chunks."""
                        result = ""
                        for ch in chunks:
                            content = (ch.get("content") or "").strip()
                            if not content:
                                continue
                            if not result:
                                result = content
                                continue
                            # Find overlap: check if last 100 chars of result appear at start of content
                            overlap_max = min(200, len(result), len(content))
                            best_overlap = 0
                            for n in range(overlap_max, 20, -1):
                                if result[-n:] == content[:n]:
                                    best_overlap = n
                                    break
                            if best_overlap > 0:
                                result += content[best_overlap:]
                            else:
                                result += " " + content
                        return result

                    page_chunks_raw: dict[int, list] = {}
                    for ch in db.get_chunks_by_source(src_obj["id"]):
                        page_chunks_raw.setdefault(ch["page_number"], []).append(ch)
                    page_texts: dict[int, str] = {p: _build_page_text(chs) for p, chs in page_chunks_raw.items()}
                    page_texts_norm = {p: _normalize_for_match(t) for p, t in page_texts.items()}


                    # Validate each answer_part's evidence — allow multiple chips per page
                    # but dedupe if two evidences share a long substring (likely the same fact)
                    validated_chips: list[dict] = []
                    seen_norms: list[str] = []
                    logger.info(f"[KARTEIKARTE] card '{c.get('front', '')[:60]}' has {len(answer_parts)} answer_parts")

                    def _is_duplicate_evidence(new_norm: str) -> bool:
                        new_words = new_norm.split()
                        if len(new_words) < 4:
                            return new_norm in seen_norms
                        for seen in seen_norms:
                            seen_words = seen.split()
                            # Check if longest common substring is ≥70% of the shorter evidence
                            shorter_len = min(len(new_words), len(seen_words))
                            threshold = max(4, int(shorter_len * 0.7))
                            # Look for any sequence of `threshold` words from new in seen
                            for i in range(len(new_words) - threshold + 1):
                                phrase = " ".join(new_words[i:i + threshold])
                                if phrase in seen:
                                    return True
                        return False

                    for part in answer_parts:
                        ev_text = (part.get("evidence") or "").strip()
                        ev_page = part.get("page_number")
                        if not ev_text or ev_page is None:
                            logger.info(f"  [PART] skipped (no evidence or page)")
                            continue
                        ev_norm = _normalize_for_match(ev_text)
                        if _is_duplicate_evidence(ev_norm):
                            logger.info(f"  [PART] dedup (overlaps existing)")
                            continue
                        logger.info(f"  [PART] page={ev_page} ev={ev_text[:80]!r}")
                        target_page: int | None = None
                        if ev_page in page_texts_norm and _evidence_matches_page(ev_norm, page_texts_norm[ev_page]):
                            target_page = ev_page
                        else:
                            for p, pt in page_texts_norm.items():
                                if _evidence_matches_page(ev_norm, pt):
                                    target_page = p
                                    break
                        if target_page is None:
                            logger.info(f"  [PART] NO MATCH on any page")
                            continue
                        logger.info(f"  [PART] matched page {target_page}")
                        seen_norms.append(ev_norm)
                        validated_chips.append({
                            "source_label": sl,
                            "page_number": target_page,
                            "start_time": _time_map.get((sl, target_page)),
                            "highlight_text": ev_text,
                        })

                    # Merge all chips on the same page into one (full span from first to last evidence)
                    def _find_orig_span(orig: str, ev_text: str) -> tuple[int, int] | None:
                        """Find a fuzzy position of ev_text inside orig. Returns (start, end) in orig."""
                        orig_norm = _normalize_for_match(orig)
                        ev_norm = _normalize_for_match(ev_text)
                        if not ev_norm:
                            return None
                        # Find position in normalized, then map to original by finding first word
                        pos_norm = orig_norm.find(ev_norm)
                        phrase_len = len(ev_norm)
                        if pos_norm < 0:
                            ev_words = ev_norm.split()
                            if len(ev_words) < 6:
                                return None
                            for window in range(min(len(ev_words), 20), 5, -1):
                                for i in range(len(ev_words) - window + 1):
                                    phrase = " ".join(ev_words[i:i + window])
                                    found = orig_norm.find(phrase)
                                    if found >= 0:
                                        pos_norm = found
                                        phrase_len = len(phrase)
                                        break
                                if pos_norm >= 0:
                                    break
                        if pos_norm < 0:
                            return None
                        # Map norm position to orig position by searching for the first few words
                        first_words = orig_norm[pos_norm:pos_norm + min(40, phrase_len)].split()
                        if not first_words:
                            return None
                        # Search in original for a sequence matching the first word(s)
                        import re as _re_find
                        for first_w in first_words[:3]:
                            if len(first_w) < 3:
                                continue
                            pattern = _re_find.escape(first_w)
                            for m in _re_find.finditer(pattern, orig, _re_find.IGNORECASE):
                                # Verify: the rest of the phrase also matches from here
                                tail_norm = _normalize_for_match(orig[m.start():m.start() + phrase_len + 100])
                                if tail_norm.startswith(orig_norm[pos_norm:pos_norm + min(30, phrase_len)]):
                                    start = m.start()
                                    # End: consume phrase_len worth of non-whitespace chars from original
                                    end = start
                                    consumed_norm = 0
                                    while end < len(orig) and consumed_norm < phrase_len:
                                        if not orig[end].isspace():
                                            consumed_norm += 1
                                        end += 1
                                    return (start, end)
                            break
                        return None

                    def _merge_page_chips(chips: list[dict]) -> list[dict]:
                        by_page: dict[int, list[dict]] = {}
                        for ch in chips:
                            pn = ch.get("page_number") or 0
                            by_page.setdefault(pn, []).append(ch)
                        merged: list[dict] = []
                        for pn, page_chips in by_page.items():
                            if len(page_chips) == 1:
                                merged.append(page_chips[0])
                                continue
                            page_orig = page_texts.get(pn, "")
                            if not page_orig:
                                merged.append(page_chips[0])
                                continue
                            # Find position of each evidence in the ORIGINAL page text
                            positions: list[tuple[int, int]] = []
                            for ch in page_chips:
                                span = _find_orig_span(page_orig, ch["highlight_text"])
                                if span:
                                    positions.append(span)
                            if not positions:
                                merged.append(page_chips[0])
                                continue
                            span_start = min(p[0] for p in positions)
                            span_end = max(p[1] for p in positions)
                            combined = page_orig[span_start:span_end].strip()
                            # Collapse internal whitespace (keep paragraph breaks)
                            combined = _re_card.sub(r"[ \t]+", " ", combined)
                            combined = _re_card.sub(r" *\n *", "\n", combined)
                            first_ch = page_chips[0]
                            merged.append({
                                "source_label": first_ch["source_label"],
                                "page_number": first_ch["page_number"],
                                "start_time": first_ch.get("start_time"),
                                "highlight_text": combined,
                            })
                        return merged

                    validated_chips = _merge_page_chips(validated_chips)

                    # Sort chips by page number (or start_time for media)
                    validated_chips.sort(key=lambda s: (
                        s.get("start_time") if s.get("start_time") is not None else (s.get("page_number") or 0),
                    ))

                    if validated_chips:
                        item["sources"] = validated_chips
                        item["source_label"] = validated_chips[0]["source_label"]
                        item["page_number"] = validated_chips[0]["page_number"]
                        item["start_time"] = validated_chips[0].get("start_time")
                    else:
                        item["source_label"] = sl
                        if answer_parts:
                            first_pn = answer_parts[0].get("page_number")
                            if first_pn is not None:
                                item["page_number"] = first_pn
                                item["start_time"] = _time_map.get((sl, first_pn))
                    return item
                items = [_parse_karteikarte(c) for c in data.get("cards", [])][:count]
                title = data.get("title", multi_label)
            else:
                tool_prompt = "Du erstellst Übungen basierend auf dem gegebenen Quelltext.\n\n"
                _source_rule = "- Gib für jede Frage source_label und page_number an — die Quelle/Seite aus der der Inhalt stammt.\n"
                if tool == "lueckentext":
                    tool_prompt += (
                        "Erstelle Lückentext-Übungen. Antworte NUR mit einem JSON-Array:\n"
                        '[{"sentence": "Satz mit ___ als Lücke", "answer": "Antwort", '
                        '"options": ["A", "B", "C", "D"], "correct_idx": 0, '
                        '"source_label": "Dateiname.pdf", "page_number": 5}]\n'
                        "WICHTIG:\n"
                        "- Verwende KEINE Personennamen in Fragen. Statt 'laut Prof. X' schreibe 'laut Quelle'.\n"
                        + _source_rule +
                        f"Erstelle genau {count} Übungen."
                    )
                elif tool == "quiz":
                    tool_prompt += (
                        "Erstelle Multiple-Choice Verständnisfragen zum gegebenen Text. "
                        "Die Fragen sollen das Verständnis des Inhalts prüfen.\n\n"
                        "Antworte NUR mit einem JSON-Array:\n"
                        '[{"question": "Verständnisfrage?", "options": ["A", "B", "C", "D"], '
                        '"correct_idx": 0, '
                        '"source_label": "Dateiname.pdf", "page_number": 5}]\n'
                        "WICHTIG:\n"
                        "- Verwende KEINE Personennamen in Fragen. Statt 'laut Prof. X' schreibe 'laut Quelle'.\n"
                        + _source_rule +
                        f"Erstelle genau {count} Fragen. Mische leichte und schwierige Fragen."
                    )
                else:
                    tool_prompt += (
                        "Erstelle ein Begriffe-Quiz: Multiple-Choice-Fragen zu Fachbegriffen aus dem Quelltext.\n\n"
                        "Identifiziere zuerst die wichtigsten Fachbegriffe im Text, dann erstelle Fragen dazu.\n"
                        "Fragetypen mischen:\n"
                        "- Was bedeutet der Begriff X?\n"
                        "- Wie lautet die englische Übersetzung von X? (bzw. deutsche Übersetzung)\n"
                        "- Welcher Fachbegriff beschreibt folgendes: [Definition]?\n\n"
                        "Wähle Fachbegriffe, die sich gut für Multiple Choice eignen "
                        "(klare Definition, plausible Distraktoren möglich).\n\n"
                        "Antworte NUR mit einem JSON-Array:\n"
                        '[{"question": "Frage zum Fachbegriff?", "options": ["A", "B", "C", "D"], '
                        '"correct_idx": 0, '
                        '"source_label": "Dateiname.pdf", "page_number": 5}]\n'
                        "WICHTIG:\n"
                        "- Verwende KEINE Personennamen in Fragen. Statt 'laut Prof. X' schreibe 'laut Quelle'.\n"
                        + _source_rule +
                        f"Erstelle genau {count} Fragen."
                    )
                messages = [
                    {"role": "system", "content": tool_prompt},
                    {"role": "user", "content": f"Quellen:\n\n{context}"},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                exercises = _json.loads(answer)
                if isinstance(exercises, list):
                    exercises = exercises[:count]
                # Build page index from context for text matching
                import re as _re
                _page_index: list[tuple[str, int, str]] = []  # (source_label, page, text)
                for line in context.split("\n"):
                    m = _re.match(r"\[(.+?),\s*S\.\s*(\d+)\]\s*(.*)", line)
                    if m:
                        _page_index.append((m.group(1), int(m.group(2)), m.group(3).lower()))

                def _find_page(search_text: str) -> tuple[str, int | None]:
                    """Match exercise text against context lines to find source + page."""
                    words = _re.findall(r"\w+", search_text.lower())
                    if not words or not _page_index:
                        return first_label, None
                    best_label, best_page, best_score = first_label, None, 0
                    for label, page, text in _page_index:
                        score = sum(1 for w in words if w in text)
                        if score > best_score:
                            best_label, best_page, best_score = label, page, score
                    return best_label, best_page

                if tool == "lueckentext":
                    items = []
                    for ex in exercises:
                        sl = ex.get("source_label") or first_label
                        pn = ex.get("page_number")
                        if not pn:
                            sl, pn = _find_page(ex["sentence"] + " " + ex["answer"])
                        items.append({"front": ex["sentence"], "back": ex["answer"], "options": ex["options"],
                            "correct_idx": ex["correct_idx"],
                            "source_label": sl, "page_number": pn,
                            "start_time": _time_map.get((sl, pn or 0))})
                else:  # quiz + vokabeltest
                    items = []
                    for q in exercises:
                        sl = q.get("source_label") or first_label
                        pn = q.get("page_number")
                        if not pn:
                            sl, pn = _find_page(q["question"] + " " + q["options"][q["correct_idx"]])
                        items.append({"front": q["question"], "back": q["options"][q["correct_idx"]], "options": q["options"],
                            "correct_idx": q["correct_idx"],
                            "source_label": sl, "page_number": pn,
                            "start_time": _time_map.get((sl, pn or 0))})
                # Generate a short descriptive title via LLM
                try:
                    title_resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "Gib einen kurzen, prägnanten Titel für diese Übung. Antworte NUR mit dem Titel, ohne Anführungszeichen."},
                            {"role": "user", "content": context[:2000]},
                        ],
                        temperature=0.3,
                        max_tokens=80,
                    )
                    title = (title_resp.choices[0].message.content or "").strip().strip('"\'')
                    if not title:
                        title = multi_label
                except Exception:
                    title = multi_label

        if not items:
            db.fail_exercise_set(set_id)
            return

        db.finalize_exercise_set(set_id, title, items)
        logger.info("KI Tutor: exercise set {} generated ({} items)", set_id, len(items))

    except Exception as e:
        logger.error("KI Tutor: exercise set {} generation failed: {}", set_id, e)
        db.fail_exercise_set(set_id)
