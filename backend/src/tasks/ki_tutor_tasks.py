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
    TUTOR_INFOGRAPHIC_PROMPT,
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
        is_small = _provider == "ollama"
        extra_body = {}
        langfuse_context.update_current_observation(
            metadata={"provider": _provider, "base_url": _base_url, "model": model},
        )

        # 4. Generate summaries
        #    Small models (ollama): parallel single-page requests
        #    Large models (cloud):  parallel batches of TUTOR_SUMMARY_BATCH_SIZE pages
        all_summaries: list[str] = [""] * len(pages)

        if is_small:
            with concurrent.futures.ThreadPoolExecutor(max_workers=TUTOR_SUMMARY_PARALLEL_WORKERS_SMALL) as executor:
                futures = {
                    executor.submit(_summarize_page, client, model, p, True, extra_body, lang): i
                    for i, p in enumerate(pages)
                }
                for future in concurrent.futures.as_completed(futures):
                    idx = futures[future]
                    all_summaries[idx] = future.result()
                    logger.info(
                        "KI Tutor: summarized page {}/{} for source {}",
                        idx + 1, len(pages), source_uuid,
                    )
        else:
            batches = [pages[i:i + TUTOR_SUMMARY_BATCH_SIZE] for i in range(0, len(pages), TUTOR_SUMMARY_BATCH_SIZE)]
            batch_summaries: list[list[str]] = [[]] * len(batches)
            with concurrent.futures.ThreadPoolExecutor(max_workers=TUTOR_SUMMARY_PARALLEL_WORKERS_LARGE) as executor:
                futures = {
                    executor.submit(_summarize_batch, client, model, batch, lang): i
                    for i, batch in enumerate(batches)
                }
                for future in concurrent.futures.as_completed(futures):
                    bidx = futures[future]
                    batch_summaries[bidx] = future.result()
                    start = bidx * TUTOR_SUMMARY_BATCH_SIZE + 1
                    end = min(start + TUTOR_SUMMARY_BATCH_SIZE - 1, len(pages))
                    logger.info(
                        "KI Tutor: summarized pages {}-{}/{} for source {}",
                        start, end, len(pages), source_uuid,
                    )
            all_summaries = [s for batch in batch_summaries for s in batch]

        # 5. Save summaries to DB (block_index=0, bbox=full page placeholder)
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
                for p, s in zip(pages, all_summaries)
                if s.strip()
            ],
        )

        # 6. Done
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
        context_parts: list[str] = []
        for sid, suuid in zip(source_ids, source_uuids):
            source = db.get_ki_tutor_source(suuid)
            source_label = source["filename"] if source else f"Quelle"
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

        # Fair budget split per source (64k total, whole summaries only)
        budget_per_source = 64000 // len(source_ids)
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
    '    {"layout": "title", "title": "Große Aussage als Titel", "subtitle": "Ergänzender Untertitel", "image_prompt": "..."},\n'
    '    {"layout": "statement", "title": "Eine starke Aussage als ganzer Satz.", "body": "2-3 Sätze Erklärung dazu."},\n'
    '    {"layout": "section_number", "number": "1", "title": "Abschnittstitel", "subtitle": "Kurzbeschreibung"},\n'
    '    {"layout": "icon_grid", "title": "Vier Vorteile auf einen Blick.", "items": [\n'
    '      {"title": "Punkt A", "body": "Kurze Erklärung in 1-2 Sätzen."},\n'
    '      {"title": "Punkt B", "body": "Kurze Erklärung."},\n'
    '      {"title": "Punkt C", "body": "Kurze Erklärung."},\n'
    '      {"title": "Punkt D", "body": "Kurze Erklärung."}\n'
    '    ]},\n'
    '    {"layout": "content", "title": "Aussage als Titel.", "bullets": ["Punkt 1", "Punkt 2", "Punkt 3"], "image_prompt": "..."},\n'
    '    {"layout": "comparison", "title": "Vergleich als Aussage.", "left_title": "Option A", "left_bullets": ["..."], "right_title": "Option B", "right_bullets": ["..."]},\n'
    '    {"layout": "quote", "title": "Kontextüberschrift", "quote": "Zitattext oder Kernaussage in Anführungszeichen.", "body": "Erklärung dazu."},\n'
    '    {"layout": "summary", "title": "Aussage: Kernbotschaft.", "bullets": ["Fazit 1", "Fazit 2", "Fazit 3"]}\n'
    "  ]\n"
    "}\n\n"
    "Layouts:\n"
    "- title: Titelfolie (1x am Anfang). image_prompt = englischer Prompt für Illustration.\n"
    "- statement: Große fette Aussage + Fließtext. Kein Bild, keine Bullets.\n"
    "- section_number: Abschnittstrenner mit großer Zahl (1, 2, 3...) + Titel + Beschreibung.\n"
    "- icon_grid: 2x2 Raster mit 4 Punkten (je title + body). Für Vorteile, Features, Übersichten.\n"
    "- content: Aussage-Titel + 3-5 Bullet Points (max 12 Wörter/Punkt) + optional image_prompt.\n"
    "- comparison: Zwei Boxen nebeneinander mit Titel + Bullets pro Seite.\n"
    "- quote: Hervorgehobenes Zitat/Kernaussage in Box + erklärende Beschreibung.\n"
    "- summary: Abschlussfolie (1x am Ende) mit Kernaussagen.\n\n"
    "Regeln:\n"
    "- {slide_count} Folien (inkl. Titel + Abschluss)\n"
    "- Titel sind IMMER vollständige Aussagesätze mit Punkt am Ende.\n"
    "- Mische die Layouts — NICHT nur 'content' Folien!\n"
    "- STICHPUNKTE statt Fließtext — max 6-8 Wörter pro Bullet. Keine ganzen Sätze in Bullets.\n"
    "- Max 5-6 Bullets pro Content-Folie. Lieber eine Folie mehr als zu viele Punkte.\n"
    "- Verwende section_number Folien um größere Abschnitte zu markieren.\n"
    "- icon_grid für Übersichten mit 4 gleichwertigen Punkten.\n"
    "- statement für einzelne starke Aussagen.\n"
    "- quote für wichtige Zitate oder Kernbotschaften.\n"
    "- image_prompt: Nur bei title und content. Englisch. Stil: 'flat vector illustration, minimal clean lines, muted soft colors, white background, no text'. Max 3 Bilder total.\n"
    "- Texte EXAKT aus der Quelle — keine Umformulierungen, keine Rechtschreibfehler.\n"
    "- Sprache = Sprache der Quelle.\n"
    "- Antworte NUR mit JSON."
)


def _generate_slide_image(prompt: str, size: str = "1024x1024") -> bytes | None:
    """Generate a flat vector illustration via FLUX for slides. Returns PNG bytes or None."""
    import httpx
    import base64
    # Enforce illustration style
    full_prompt = f"{prompt}, flat vector illustration style, minimal clean lines, muted soft colors, white background, no text, no watermark"
    try:
        from src.dependencies import _resolve_llm_provider
        _api_key, _base_url, _, _ = _resolve_llm_provider()
        img_base = _base_url.rstrip("/v1").rstrip("/")
        img_url = f"{img_base}/v1/images/generations"
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                img_url,
                headers={"Authorization": f"Bearer {_api_key}"},
                json={"model": "flux", "prompt": full_prompt, "size": size, "n": 1, "response_format": "b64_json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                imgs = data.get("data", [])
                if imgs:
                    return base64.b64decode(imgs[0]["b64_json"])
    except Exception as e:
        logger.warning("FLUX image failed: {}", e)
    return None


def _build_pptx(slides_data: list[dict], images: dict[int, bytes]) -> bytes:
    """Build PPTX in NotebookLM style: warm white bg, bold statements, clean layout."""
    from pptx import Presentation as PptxPresentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    import io
    import tempfile

    # Colors
    BG = RGBColor(0xFF, 0xFF, 0xFF)            # white background
    DARK = RGBColor(0x1A, 0x1A, 0x1A)          # near-black for text
    BRAND = RGBColor(0x00, 0x42, 0x61)         # THL dark blue
    ACCENT = RGBColor(0x0E, 0x74, 0x90)        # teal
    MUTED = RGBColor(0x6B, 0x72, 0x80)         # gray
    BOX_GREEN = RGBColor(0x3B, 0x82, 0x78)     # muted teal for boxes
    BOX_BLUE = RGBColor(0x3B, 0x5E, 0x8C)      # muted blue for boxes
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    FONT = "Calibri"
    W = Inches(13.333)
    H = Inches(7.5)

    prs = PptxPresentation()
    prs.slide_width = W
    prs.slide_height = H
    blank = prs.slide_layouts[6]

    def _bg(sl, color=None):
        sh = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
        sh.fill.solid()
        sh.fill.fore_color.rgb = color or BG
        sh.line.fill.background()

    def _box(sl, left, top, w, h, color):
        sh = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
        sh.fill.solid()
        sh.fill.fore_color.rgb = color
        sh.line.fill.background()
        return sh

    def _txt(sl, left, top, w, h, text, size=18, bold=False, color=DARK, align=PP_ALIGN.LEFT, italic=False):
        tb = sl.shapes.add_textbox(left, top, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.color.rgb = color
        r.font.name = FONT
        return tb

    def _bullets_box(sl, left, top, w, h, items, size=15, color=DARK, bc=ACCENT):
        if not items:
            return
        tb = sl.shapes.add_textbox(left, top, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        for i, txt in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_before = Pt(10)
            p.space_after = Pt(4)
            r1 = p.add_run()
            r1.text = "\u2022  "
            r1.font.size = Pt(size)
            r1.font.bold = True
            r1.font.color.rgb = bc
            r1.font.name = FONT
            r2 = p.add_run()
            r2.text = txt
            r2.font.size = Pt(size)
            r2.font.color.rgb = color
            r2.font.name = FONT

    def _img(sl, img_bytes, left, top, max_w, max_h):
        """Add image preserving aspect ratio within max_w x max_h box (all args in EMU)."""
        from PIL import Image as PILImage
        pil = PILImage.open(io.BytesIO(img_bytes))
        iw, ih = pil.size  # pixels
        if not iw or not ih:
            return
        img_ratio = iw / ih  # e.g. 1.78 for 16:9
        box_ratio = max_w / max_h
        # Fit image into box preserving aspect ratio
        if img_ratio > box_ratio:
            # Image is wider than box → fit to width
            final_w = max_w
            final_h = int(max_w / img_ratio)
        else:
            # Image is taller than box → fit to height
            final_h = max_h
            final_w = int(max_h * img_ratio)
        # Center within box
        offset_x = (max_w - final_w) // 2
        offset_y = (max_h - final_h) // 2
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(img_bytes)
            path = tmp.name
        try:
            sl.shapes.add_picture(path, left + offset_x, top + offset_y, final_w, final_h)
        finally:
            os.unlink(path)

    def _snum(sl, idx):
        _txt(sl, Inches(12.3), Inches(7.05), Inches(0.8), Inches(0.3),
             f"{idx + 1}", size=8, color=MUTED, align=PP_ALIGN.RIGHT)

    def _watermark(sl):
        """Small branding mark bottom-right."""
        _txt(sl, Inches(11.5), Inches(7.05), Inches(1.5), Inches(0.3),
             "TH Lübeck", size=7, color=MUTED, align=PP_ALIGN.RIGHT)

    total = len(slides_data)
    section_counter = 0

    for idx, s in enumerate(slides_data):
        lay = s.get("layout", "content")
        img_bytes = images.get(idx)
        sl = prs.slides.add_slide(blank)
        _bg(sl)

        if lay == "title":
            # Large title left, illustration right
            _txt(sl, Inches(1), Inches(1.5), Inches(7), Inches(3.5),
                 s.get("title", ""), size=40, bold=True, color=DARK)
            if s.get("subtitle"):
                _txt(sl, Inches(1), Inches(5), Inches(7), Inches(1.2),
                     s["subtitle"], size=18, color=MUTED)
            if img_bytes:
                _img(sl, img_bytes, Inches(8.5), Inches(1), Inches(4), Inches(5))
            _watermark(sl)

        elif lay == "statement":
            # Big bold statement centered, body text below
            _txt(sl, Inches(1), Inches(1.2), Inches(11), Inches(2.5),
                 s.get("title", ""), size=36, bold=True, color=DARK)
            if s.get("body"):
                _txt(sl, Inches(1), Inches(3.8), Inches(10), Inches(2.5),
                     s["body"], size=16, color=MUTED)
            _snum(sl, idx)

        elif lay == "section_number":
            # Corporate design background for chapter announcements
            sl.shapes[0].fill.fore_color.rgb = BRAND  # override white bg
            section_counter += 1
            num = s.get("number", str(section_counter))
            _txt(sl, Inches(1), Inches(1), Inches(4), Inches(5),
                 num, size=120, bold=True, color=WHITE)
            _txt(sl, Inches(5), Inches(2.2), Inches(7), Inches(2),
                 s.get("title", ""), size=32, bold=True, color=WHITE)
            if s.get("subtitle"):
                _txt(sl, Inches(5), Inches(4.2), Inches(7), Inches(1.5),
                     s["subtitle"], size=16, color=RGBColor(0xBB, 0xD5, 0xE8))
            _snum(sl, idx)

        elif lay == "icon_grid":
            # Title top, 2x2 grid with icon circles + title + body
            _txt(sl, Inches(1), Inches(0.5), Inches(11), Inches(1.2),
                 s.get("title", ""), size=28, bold=True, color=DARK)
            items = s.get("items", [])[:4]
            # Unicode icons for visual variety
            icons = ["\u2713", "\u26A1", "\u2605", "\u2192"]  # ✓ ⚡ ★ →
            grid = [
                (Inches(1), Inches(2.2)),
                (Inches(7), Inches(2.2)),
                (Inches(1), Inches(4.8)),
                (Inches(7), Inches(4.8)),
            ]
            icon_colors = [ACCENT, BRAND, BOX_GREEN, BOX_BLUE]
            for i, item in enumerate(items):
                if i >= 4:
                    break
                gx, gy = grid[i]
                ic = icon_colors[i % 4]
                # Icon circle
                circle = sl.shapes.add_shape(MSO_SHAPE.OVAL, gx, gy, Inches(0.6), Inches(0.6))
                circle.fill.solid()
                circle.fill.fore_color.rgb = ic
                circle.line.fill.background()
                # Icon symbol inside circle
                _txt(sl, gx + Inches(0.08), gy + Inches(0.05), Inches(0.44), Inches(0.5),
                     icons[i % 4], size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
                # Title
                _txt(sl, gx + Inches(0.8), gy, Inches(4.2), Inches(0.5),
                     item.get("title", ""), size=16, bold=True, color=DARK)
                # Body
                _txt(sl, gx + Inches(0.8), gy + Inches(0.6), Inches(4.2), Inches(1.4),
                     item.get("body", ""), size=13, color=MUTED)
            _snum(sl, idx)

        elif lay == "comparison":
            # Title + two boxes side by side
            _txt(sl, Inches(1), Inches(0.6), Inches(11), Inches(1.2),
                 s.get("title", ""), size=28, bold=True, color=DARK)
            # Left box
            _box(sl, Inches(0.8), Inches(2.2), Inches(5.5), Inches(4.5), BOX_GREEN)
            if s.get("left_title"):
                _txt(sl, Inches(1.2), Inches(2.5), Inches(4.8), Inches(0.5),
                     s["left_title"], size=16, bold=True, color=WHITE)
            _bullets_box(sl, Inches(1.2), Inches(3.2), Inches(4.8), Inches(3.2),
                         s.get("left_bullets", []), size=14, color=WHITE, bc=WHITE)
            # Arrow between
            _txt(sl, Inches(6.1), Inches(3.8), Inches(1.1), Inches(0.8),
                 "\u2192", size=36, bold=True, color=BRAND, align=PP_ALIGN.CENTER)
            # Right box
            _box(sl, Inches(7), Inches(2.2), Inches(5.5), Inches(4.5), BOX_BLUE)
            if s.get("right_title"):
                _txt(sl, Inches(7.4), Inches(2.5), Inches(4.8), Inches(0.5),
                     s["right_title"], size=16, bold=True, color=WHITE)
            _bullets_box(sl, Inches(7.4), Inches(3.2), Inches(4.8), Inches(3.2),
                         s.get("right_bullets", []), size=14, color=WHITE, bc=WHITE)
            _snum(sl, idx)

        elif lay == "quote":
            # Title top, quote in rounded box, body below
            if s.get("title"):
                _txt(sl, Inches(1), Inches(0.8), Inches(11), Inches(1),
                     s["title"], size=24, bold=True, color=DARK)
            # Quote box
            _box(sl, Inches(1.5), Inches(2.2), Inches(10), Inches(2.5), RGBColor(0xF3, 0xF4, 0xF6))
            quote_text = s.get("quote", "")
            _txt(sl, Inches(2.2), Inches(2.5), Inches(9), Inches(2),
                 f"\u201E{quote_text}\u201C", size=16, italic=True, color=DARK)
            if s.get("body"):
                _txt(sl, Inches(1.5), Inches(5.2), Inches(10), Inches(1.5),
                     s["body"], size=14, color=MUTED)
            _snum(sl, idx)

        elif lay == "summary":
            # Final slide with key takeaways
            _txt(sl, Inches(1), Inches(0.8), Inches(11), Inches(1.5),
                 s.get("title", "Zusammenfassung"), size=32, bold=True, color=DARK)
            items = s.get("bullets", [])
            if items:
                tb = sl.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11), Inches(4.5))
                tf = tb.text_frame
                tf.word_wrap = True
                for i, txt in enumerate(items):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.space_before = Pt(14)
                    p.space_after = Pt(6)
                    r1 = p.add_run()
                    r1.text = f"\u2022  "
                    r1.font.size = Pt(16)
                    r1.font.bold = True
                    r1.font.color.rgb = ACCENT
                    r1.font.name = FONT
                    r2 = p.add_run()
                    r2.text = txt
                    r2.font.size = Pt(16)
                    r2.font.color.rgb = DARK
                    r2.font.name = FONT
            _watermark(sl)
            _snum(sl, idx)

        else:  # content
            # Title + bullets left, optional image right
            _txt(sl, Inches(1), Inches(0.6), Inches(7) if img_bytes else Inches(11), Inches(1.2),
                 s.get("title", ""), size=28, bold=True, color=DARK)
            bullet_w = Inches(6.5) if img_bytes else Inches(10)
            _bullets_box(sl, Inches(1), Inches(2), bullet_w, Inches(4.8),
                         s.get("bullets", []), size=15, color=DARK, bc=ACCENT)
            if img_bytes:
                _img(sl, img_bytes, Inches(8.2), Inches(1.2), Inches(4.3), Inches(5.3))
            _snum(sl, idx)

        if s.get("notes"):
            sl.notes_slide.notes_text_frame.text = s["notes"]

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@celery_app.task(bind=True, name="ki_tutor.generate_presentation", queue="general",
                 soft_time_limit=600, time_limit=660)
@observe(name="ki-tutor-presentation")
def run_generate_presentation(self, presentation_id: int, source_id: int, source_uuid: str, slide_count: int = 12):
    """Generate a presentation from a single source (NotebookLM-style + FLUX images)."""
    import json as _json

    try:
        db.update_ki_tutor_presentation(presentation_id, "running")
        logger.info("KI Tutor: generating presentation {}", presentation_id)

        source = db.get_ki_tutor_source(source_uuid)
        source_label = source["filename"] if source else "Quelle"
        summaries = db.get_paragraph_summaries_by_source(source_id)

        if summaries:
            pages: dict[int, list[str]] = {}
            for s in summaries:
                pages.setdefault(s["page_number"], []).append(s["summary"])
            parts = [f"[{source_label}, S. {p}] {' '.join(texts)}" for p, texts in sorted(pages.items())]
            context = f"--- {source_label} ---\n" + "\n".join(parts)
        else:
            chunks = db.get_chunks_by_source(source_id)
            if chunks:
                parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks[:40]]
                context = f"--- {source_label} ---\n" + "\n".join(parts)
            else:
                db.update_ki_tutor_presentation(presentation_id, "failed", error="Keine Inhalte vorhanden")
                return

        context = context[:20000]

        from langfuse.openai import OpenAI
        from src.dependencies import _resolve_llm_provider
        _api_key, _base_url, _model, _provider = _resolve_llm_provider()
        client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=240)
        langfuse_context.update_current_observation(
            metadata={"provider": _provider, "base_url": _base_url, "model": _model},
        )

        prompt = _PRES_PROMPT.replace("{slide_count}", str(slide_count))
        response = client.chat.completions.create(
            model=_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"/no_think\nErstelle eine Präsentation aus folgender Quelle:\n\n{context}"},
            ],
            temperature=0.3,
        )

        raw = response.choices[0].message.content
        if not raw:
            db.update_ki_tutor_presentation(presentation_id, "failed", error="LLM returned empty content")
            return

        answer = raw.strip()
        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if "<think>" in answer:
            think_end = answer.find("</think>")
            if think_end != -1:
                answer = answer[think_end + 8:].strip()

        data = _json.loads(answer)
        if not isinstance(data, dict) or "slides" not in data:
            db.update_ki_tutor_presentation(presentation_id, "failed", error="Invalid presentation format")
            return

        pres_title = data.get("title", source_label)
        slides = data["slides"][:20]

        # Generate FLUX images (max 4, parallel)
        images: dict[int, bytes] = {}
        image_tasks = [(i, s["image_prompt"]) for i, s in enumerate(slides) if s.get("image_prompt")][:4]
        if image_tasks:
            logger.info("KI Tutor: generating {} FLUX images", len(image_tasks))
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor(max_workers=2) as pool:
                futures = {pool.submit(_generate_slide_image, p): i for i, p in image_tasks}
                for f in _cf.as_completed(futures):
                    i = futures[f]
                    img = f.result()
                    if img:
                        images[i] = img
            logger.info("KI Tutor: {} images generated", len(images))

        from src.templates.pptx_builder import build_pptx
        pptx_bytes = build_pptx(pres_title, slides, images)

        from src.storage import save_file
        pres = db.get_ki_tutor_presentation(presentation_id)
        pptx_path = save_file(pres["user_id"], f"presentation_{presentation_id}.pptx", pptx_bytes)

        db.update_ki_tutor_presentation(
            presentation_id, "success",
            title=pres_title, slides=slides, pptx_path=pptx_path,
        )
        logger.info("KI Tutor: presentation {} done ({} slides, {} images)", presentation_id, len(slides), len(images))

    except Exception as e:
        logger.error("KI Tutor: presentation {} failed: {}", presentation_id, e)
        db.update_ki_tutor_presentation(presentation_id, "failed", error=str(e))


# ── Infographic generation ────────────────────────────────────────────────────

# SVG style presets
_INFOGRAPHIC_STYLES = {
    "professional": {
        "bg": "#FFFFFF",
        "header_bg": "#004261",
        "header_text": "#FFFFFF",
        "accent": "#0E7490",
        "section_bg": "#F0F9FF",
        "text": "#1E293B",
        "muted": "#64748B",
        "stat_value": "#004261",
        "border": "#E2E8F0",
        "icon_colors": ["#0E7490", "#166534", "#A16207", "#534AB7", "#B91C1C", "#0369A1"],
    },
    "scientific": {
        "bg": "#FAFAFA",
        "header_bg": "#1E293B",
        "header_text": "#F8FAFC",
        "accent": "#3B82F6",
        "section_bg": "#F1F5F9",
        "text": "#0F172A",
        "muted": "#475569",
        "stat_value": "#1D4ED8",
        "border": "#CBD5E1",
        "icon_colors": ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444", "#06B6D4"],
    },
    "modern": {
        "bg": "#0F172A",
        "header_bg": "#6366F1",
        "header_text": "#FFFFFF",
        "accent": "#818CF8",
        "section_bg": "#1E293B",
        "text": "#E2E8F0",
        "muted": "#94A3B8",
        "stat_value": "#A5B4FC",
        "border": "#334155",
        "icon_colors": ["#818CF8", "#34D399", "#FBBF24", "#F472B6", "#FB923C", "#22D3EE"],
    },
}


def _escape_svg(text: str) -> str:
    """Escape text for safe SVG embedding."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _wrap_text(text: str, max_chars: int = 45) -> list[str]:
    """Word-wrap text into lines of max_chars."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        if current and len(current) + 1 + len(w) > max_chars:
            lines.append(current)
            current = w
        else:
            current = f"{current} {w}" if current else w
    if current:
        lines.append(current)
    return lines or [""]


def _generate_flux_image(base_url: str, api_key: str, prompt: str, size: str = "1024x1024") -> str | None:
    """Call KISSKI Flux to generate an image, return base64 or None."""
    import httpx
    try:
        with httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=180.0,
        ) as client:
            resp = client.post(
                f"{base_url}/images/generations",
                json={"model": "flux", "prompt": prompt, "size": size, "n": 1, "response_format": "b64_json"},
            )
        if resp.status_code == 200:
            images = resp.json().get("data", [])
            if images and "b64_json" in images[0]:
                return images[0]["b64_json"]
    except Exception as e:
        logger.warning("Flux image generation failed: {}", e)
    return None


def _build_infographic_svg(data: dict, style_name: str = "professional",
                           hero_image_b64: str | None = None,
                           section_images: dict[int, str] | None = None) -> str:
    """Build an SVG infographic with embedded Flux illustrations + text.

    Design principles:
    - Visual flow via a vertical accent line on the left
    - Alternating image placement (left/right) per section
    - Stats as inline large numbers (no card borders)
    - Hero image as full-width banner
    - Generous whitespace
    """
    s = _INFOGRAPHIC_STYLES.get(style_name, _INFOGRAPHIC_STYLES["professional"])
    F = 'font-family="Inter, system-ui, sans-serif"'
    section_images = section_images or {}

    title = _escape_svg(data.get("title", "Infografik"))
    subtitle = _escape_svg(data.get("subtitle", ""))
    sections = data.get("sections", [])

    width = 800
    pad = 32
    content_w = width - pad * 2
    img_w = 180  # section illustration width
    img_h = 180
    y = 0

    parts: list[str] = []

    # ── Hero ──────────────────────────────────────────────────────────────────
    if hero_image_b64:
        hero_h = 240
        parts.append(
            f'<defs><clipPath id="hc"><rect x="0" y="0" width="{width}" height="{hero_h}" rx="12"/></clipPath></defs>'
        )
        parts.append(
            f'<image href="data:image/png;base64,{hero_image_b64}" x="0" y="0" '
            f'width="{width}" height="{hero_h}" preserveAspectRatio="xMidYMid slice" clip-path="url(#hc)"/>'
        )
        # Gradient overlay (bottom heavier for text)
        parts.append(
            f'<linearGradient id="ho" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{s["header_bg"]}" stop-opacity="0.3"/>'
            f'<stop offset="60%" stop-color="{s["header_bg"]}" stop-opacity="0.55"/>'
            f'<stop offset="100%" stop-color="{s["header_bg"]}" stop-opacity="0.85"/>'
            f'</linearGradient>'
        )
        parts.append(f'<rect x="0" y="0" width="{width}" height="{hero_h}" fill="url(#ho)" rx="12"/>')
        # Title
        title_lines = _wrap_text(title, 40)
        ty = hero_h - 28 - (len(title_lines) - 1) * 32 - (20 if subtitle else 0)
        for ti, tl in enumerate(title_lines):
            parts.append(
                f'<text x="{pad}" y="{ty + ti * 32}" {F} font-size="26" font-weight="700" fill="#FFFFFF">'
                f'{_escape_svg(tl)}</text>'
            )
        if subtitle:
            sub_lines = _wrap_text(subtitle, 60)
            sub_y = ty + len(title_lines) * 32 + 2
            for si_l, sl in enumerate(sub_lines):
                parts.append(
                    f'<text x="{pad}" y="{sub_y + si_l * 18}" {F} font-size="13" fill="#FFFFFF" opacity="0.85">'
                    f'{_escape_svg(sl)}</text>'
                )
        y = hero_h + 32
    else:
        title_lines = _wrap_text(title, 48)
        header_h = 36 + len(title_lines) * 30 + (20 if subtitle else 0)
        parts.append(f'<rect x="0" y="0" width="{width}" height="{header_h}" fill="{s["header_bg"]}" rx="12"/>')
        for ti, tl in enumerate(title_lines):
            parts.append(
                f'<text x="{pad}" y="{30 + ti * 30}" {F} font-size="22" font-weight="700" fill="{s["header_text"]}">'
                f'{_escape_svg(tl)}</text>'
            )
        if subtitle:
            sub_y = 30 + len(title_lines) * 30
            sub_lines = _wrap_text(subtitle, 60)
            for si_l, sl in enumerate(sub_lines):
                parts.append(
                    f'<text x="{pad}" y="{sub_y + si_l * 18}" {F} font-size="13" fill="{s["header_text"]}" opacity="0.8">'
                    f'{_escape_svg(sl)}</text>'
                )
            header_h = max(header_h, sub_y + len(sub_lines) * 18 + 12)
            parts[0] = f'<rect x="0" y="0" width="{width}" height="{header_h}" fill="{s["header_bg"]}" rx="12"/>'
        y = header_h + 32

    # ── Flow line start position ──────────────────────────────────────────────
    flow_x = pad + 3
    flow_y_start = y

    # ── Sections ──────────────────────────────────────────────────────────────
    for si, section in enumerate(sections):
        sec_type = section.get("type", "list")
        heading = _escape_svg(section.get("heading", ""))
        items = section.get("items", [])
        color = s["icon_colors"][si % len(s["icon_colors"])]
        sec_img = section_images.get(si)
        img_on_right = si % 2 == 1  # alternate sides

        sec_y_start = y

        # Flow dot
        parts.append(f'<circle cx="{flow_x}" cy="{y + 10}" r="5" fill="{color}"/>')

        # ── Section heading ───────────────────────────────────────────────────
        parts.append(
            f'<text x="{pad + 18}" y="{y + 15}" {F} font-size="16" font-weight="700" fill="{s["text"]}">'
            f'{heading}</text>'
        )
        y += 30

        # ── Calculate text area based on image placement ──────────────────────
        if sec_img:
            if img_on_right:
                ix = width - pad - img_w
                tx = pad + 18
                tw = content_w - img_w - 28
            else:
                ix = pad + 18
                tx = pad + 18 + img_w + 16
                tw = content_w - img_w - 34
            # Rounded clip for image
            clip_id = f"sc{si}"
            parts.append(
                f'<defs><clipPath id="{clip_id}"><rect x="{ix}" y="{y}" width="{img_w}" height="{img_h}" rx="10"/></clipPath></defs>'
            )
            parts.append(
                f'<image href="data:image/png;base64,{sec_img}" x="{ix}" y="{y}" '
                f'width="{img_w}" height="{img_h}" preserveAspectRatio="xMidYMid slice" clip-path="url(#{clip_id})"/>'
            )
        else:
            tx = pad + 18
            tw = content_w - 18

        chars = max(20, tw // 7)

        # ── Render section content ────────────────────────────────────────────
        if sec_type == "stats":
            for item in items:
                val = _escape_svg(str(item.get("value", "")))
                label = _escape_svg(item.get("label", ""))
                desc = _escape_svg(item.get("description", ""))
                # Large number + label on same line, description below
                parts.append(
                    f'<text x="{tx}" y="{y + 22}" {F} font-size="28" font-weight="800" fill="{s["stat_value"]}">'
                    f'{val}</text>'
                )
                # Estimate val width (~16px per char at size 28)
                val_offset = len(val) * 16 + 10
                parts.append(
                    f'<text x="{tx + val_offset}" y="{y + 18}" {F} font-size="13" font-weight="600" fill="{s["text"]}">'
                    f'{label}</text>'
                )
                if desc:
                    parts.append(
                        f'<text x="{tx}" y="{y + 40}" {F} font-size="11" fill="{s["muted"]}">{desc}</text>'
                    )
                    y += 52
                else:
                    y += 38

        elif sec_type == "process":
            for pi, item in enumerate(items):
                label = _escape_svg(item.get("label", ""))
                desc = item.get("description", "")
                desc_lines = _wrap_text(desc, chars - 6) if desc else []
                # Step number circle
                cx_s = tx + 12
                cy_s = y + 12
                parts.append(f'<circle cx="{cx_s}" cy="{cy_s}" r="11" fill="{color}"/>')
                parts.append(
                    f'<text x="{cx_s}" y="{cy_s + 4}" text-anchor="middle" '
                    f'{F} font-size="11" font-weight="700" fill="#FFF">{pi + 1}</text>'
                )
                # Connector
                step_h = max(34, 20 + len(desc_lines) * 14 + 8)
                if pi < len(items) - 1:
                    parts.append(
                        f'<line x1="{cx_s}" y1="{cy_s + 11}" x2="{cx_s}" y2="{y + step_h + 1}" '
                        f'stroke="{color}" stroke-width="1.5" stroke-opacity="0.3"/>'
                    )
                # Text
                parts.append(
                    f'<text x="{tx + 32}" y="{y + 16}" {F} font-size="13" font-weight="600" fill="{s["text"]}">'
                    f'{label}</text>'
                )
                for di, dl in enumerate(desc_lines):
                    parts.append(
                        f'<text x="{tx + 32}" y="{y + 30 + di * 14}" {F} font-size="11" fill="{s["muted"]}">'
                        f'{_escape_svg(dl)}</text>'
                    )
                y += step_h + 6

        elif sec_type == "comparison":
            cols = min(len(items), 2)
            gap = 12
            col_w = (tw - gap * (cols - 1)) // cols
            max_h = 0
            col_parts: list[str] = []
            for ci, item in enumerate(items):
                bx = tx + ci * (col_w + gap)
                label = _escape_svg(item.get("label", ""))
                val = _escape_svg(str(item.get("value", "")))
                desc = item.get("description", "")
                desc_lines = _wrap_text(desc, col_w // 7) if desc else []
                item_color = s["icon_colors"][ci % len(s["icon_colors"])]
                # Left accent bar instead of full border
                ch = 28 + (18 if val else 0) + len(desc_lines) * 14 + 16
                max_h = max(max_h, ch)
                col_parts.append(
                    f'<rect x="{bx}" y="{y}" width="4" height="{ch}" fill="{item_color}" rx="2"/>'
                )
                col_parts.append(
                    f'<rect x="{bx}" y="{y}" width="{col_w}" height="{ch}" fill="{s["section_bg"]}" rx="6" opacity="0.5"/>'
                )
                ly = y + 20
                col_parts.append(
                    f'<text x="{bx + 14}" y="{ly}" {F} font-size="13" font-weight="700" fill="{item_color}">'
                    f'{label}</text>'
                )
                if val:
                    ly += 18
                    col_parts.append(
                        f'<text x="{bx + 14}" y="{ly}" {F} font-size="12" font-weight="600" fill="{s["text"]}">'
                        f'{val}</text>'
                    )
                for di, dl in enumerate(desc_lines):
                    col_parts.append(
                        f'<text x="{bx + 14}" y="{ly + 16 + di * 14}" {F} font-size="11" fill="{s["muted"]}">'
                        f'{_escape_svg(dl)}</text>'
                    )
            parts.extend(col_parts)
            y += max_h + 8

        elif sec_type == "quote":
            item = items[0] if items else {"label": ""}
            quote_text = item.get("label", "")
            quote_lines = _wrap_text(quote_text, max(20, (tw - 30) // 7))
            qh = 20 + len(quote_lines) * 20
            parts.append(f'<rect x="{tx}" y="{y}" width="4" height="{qh}" fill="{color}" rx="2"/>')
            for qi, ql in enumerate(quote_lines):
                parts.append(
                    f'<text x="{tx + 16}" y="{y + 18 + qi * 20}" {F} font-size="14" font-style="italic" '
                    f'font-weight="500" fill="{s["text"]}">{_escape_svg(ql)}</text>'
                )
            y += qh + 8

        else:  # list
            for item in items:
                label = _escape_svg(item.get("label", ""))
                desc = item.get("description", "")
                # Colored bullet
                parts.append(f'<circle cx="{tx + 5}" cy="{y + 9}" r="3.5" fill="{color}"/>')
                parts.append(
                    f'<text x="{tx + 16}" y="{y + 13}" {F} font-size="13" font-weight="600" fill="{s["text"]}">'
                    f'{label}</text>'
                )
                if desc:
                    desc_lines = _wrap_text(desc, chars - 3)
                    for di, dl in enumerate(desc_lines):
                        parts.append(
                            f'<text x="{tx + 16}" y="{y + 28 + di * 14}" {F} font-size="11" fill="{s["muted"]}">'
                            f'{_escape_svg(dl)}</text>'
                        )
                    y += 20 + len(desc_lines) * 14
                else:
                    y += 24

        # Ensure y clears the section image
        if sec_img:
            y = max(y, sec_y_start + 30 + img_h + 8)

        y += 28  # section gap

    # ── Flow line (behind everything, drawn first but added last via reorder) ─
    flow_y_end = y - 20
    flow_line = (
        f'<line x1="{flow_x}" y1="{flow_y_start}" x2="{flow_x}" y2="{flow_y_end}" '
        f'stroke="{s["border"]}" stroke-width="2" stroke-opacity="0.4"/>'
    )

    # ── Assemble SVG ──────────────────────────────────────────────────────────
    total_h = y + 16
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {width} {total_h}" width="{width}" height="{total_h}">\n'
        f'<rect width="{width}" height="{total_h}" fill="{s["bg"]}" rx="12"/>\n'
        f'{flow_line}\n'
        + "\n".join(parts)
        + "\n</svg>"
    )
    return svg


@celery_app.task(bind=True, name="ki_tutor.generate_infographic", queue="ki_tutor",
                 soft_time_limit=600, time_limit=660)
@observe(name="ki-tutor-infographic")
def run_generate_infographic(self, infographic_id: int, source_ids: list[int],
                             source_uuids: list[str], style: str = "professional"):
    """Generate infographic: LLM creates layout JSON, Flux generates illustrations, frontend renders as HTML."""
    import json as _json
    from src.config import Settings

    try:
        db.update_ki_tutor_infographic(infographic_id, "running")
        logger.info("KI Tutor: generating infographic {}", infographic_id)

        # 1. Build context from page summaries (with fallback to chunks)
        context_parts: list[str] = []
        for sid, suuid in zip(source_ids, source_uuids):
            source = db.get_ki_tutor_source(suuid)
            source_label = source["filename"] if source else "Quelle"
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
            db.update_ki_tutor_infographic(infographic_id, "failed", error="Keine Inhalte vorhanden")
            return

        budget_per_source = 16000 // len(source_ids)
        trimmed_parts = [p[:budget_per_source] for p in context_parts]
        context = "\n\n".join(trimmed_parts)

        # 2. LLM generates layout JSON
        from langfuse.openai import OpenAI
        from src.dependencies import _resolve_llm_provider
        _api_key, _base_url, _model, _provider = _resolve_llm_provider()
        client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=240)
        langfuse_context.update_current_observation(
            metadata={"provider": _provider, "base_url": _base_url, "model": _model},
        )

        style_hints = {
            "professional": "Professional corporate style. color_scheme: blue.",
            "scientific": "Scientific academic style. color_scheme: teal.",
            "modern": "Modern bold design. color_scheme: purple.",
        }

        messages = [
            {"role": "system", "content": TUTOR_INFOGRAPHIC_PROMPT},
            {"role": "user", "content": (
                f"/no_think\nErstelle eine Infografik aus folgenden Quellen.\n"
                f"Stil: {style_hints.get(style, style_hints['professional'])}\n\n{context}"
            )},
        ]

        response = client.chat.completions.create(model=_model, messages=messages, temperature=0.3)
        raw = response.choices[0].message.content
        if not raw:
            db.update_ki_tutor_infographic(infographic_id, "failed", error="LLM returned empty content")
            return

        answer = raw.strip()
        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if answer.startswith("<think>"):
            think_end = answer.find("</think>")
            if think_end != -1:
                answer = answer[think_end + 8:].strip()

        layout = _json.loads(answer)
        if not isinstance(layout, dict) or "sections" not in layout:
            db.update_ki_tutor_infographic(infographic_id, "failed", error="Invalid layout format")
            return

        ig_title = layout.get("title", "Infografik")
        logger.info("KI Tutor: infographic {} — layout generated ({} sections)", infographic_id, len(layout["sections"]))

        # 3. Collect Flux prompts and generate images in parallel
        settings = Settings()
        flux_available = bool(settings.kisski_api_key)
        image_tasks: list[tuple[str, str]] = []

        hero_prompt = layout.get("hero_prompt", "")
        if hero_prompt and flux_available:
            image_tasks.append(("hero", hero_prompt))

        for si, section in enumerate(layout["sections"]):
            if section.get("type") == "image_row":
                for ii, item in enumerate(section.get("items", [])[:3]):
                    fp = item.get("flux_prompt", "")
                    if fp and flux_available:
                        image_tasks.append((f"sec_{si}_item_{ii}", fp))

        if image_tasks:
            base_url = settings.kisski_base_url.rstrip("/")
            api_key = settings.kisski_api_key
            logger.info("KI Tutor: infographic {} — generating {} Flux images", infographic_id, len(image_tasks))

            def _gen(task: tuple[str, str]) -> tuple[str, str | None]:
                key, prompt = task
                size = "1280x720" if key == "hero" else "1024x1024"
                return key, _generate_flux_image(base_url, api_key, prompt, size)

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                results = list(pool.map(_gen, image_tasks))

            # Embed base64 images back into the layout JSON
            for key, b64 in results:
                if not b64:
                    continue
                if key == "hero":
                    layout["hero_image"] = b64
                elif key.startswith("sec_"):
                    # e.g. "sec_2_item_0"
                    parts_k = key.split("_")
                    sec_idx = int(parts_k[1])
                    item_idx = int(parts_k[3])
                    try:
                        layout["sections"][sec_idx]["items"][item_idx]["image"] = b64
                    except (IndexError, KeyError):
                        pass

            img_count = sum(1 for _, b in results if b)
            logger.info("KI Tutor: infographic {} — {} Flux images generated", infographic_id, img_count)

        # 4. Save layout JSON (frontend renders it as React components)
        db.update_ki_tutor_infographic(infographic_id, "success", title=ig_title, layout_data=layout)
        logger.info("KI Tutor: infographic {} generated successfully", infographic_id)

    except Exception as e:
        logger.error("KI Tutor: infographic {} generation failed: {}", infographic_id, e)
        db.update_ki_tutor_infographic(infographic_id, "failed", error=str(e))


# ── Shared helpers ───────────────────────────────────────────────────────────

def _get_llm_client(timeout: int = 240):
    """Create LLM client for Celery tasks. Returns (client, model, provider)."""
    from langfuse.openai import OpenAI
    from src.dependencies import _resolve_llm_provider
    _api_key, _base_url, _model, _provider = _resolve_llm_provider()
    client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=timeout)
    langfuse_context.update_current_observation(
        metadata={"provider": _provider, "base_url": _base_url, "model": _model},
    )
    return client, _model, _provider


def _clean_llm_json(raw: str) -> str:
    """Strip code fences and <think> tags from LLM output to get clean JSON."""
    answer = raw.strip()
    if answer.startswith("```"):
        answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    if answer.startswith("<think>"):
        think_end = answer.find("</think>")
        if think_end != -1:
            answer = answer[think_end + 8:].strip()
    return answer


def _build_source_context(source_ids: list[int], source_uuids: list[str],
                          max_chars: int = 16000) -> str:
    """Build text context from page summaries (falling back to chunks).

    Fairly splits budget across sources. Used by multiple generation tasks.
    """
    budget_per_source = max_chars // max(len(source_ids), 1)
    context_parts: list[str] = []
    for sid, suuid in zip(source_ids, source_uuids):
        source = db.get_ki_tutor_source(suuid)
        source_label = source["filename"] if source else "Quelle"
        summaries = db.get_paragraph_summaries_by_source(sid)
        if summaries:
            pages: dict[int, list[str]] = {}
            for s in summaries:
                pages.setdefault(s["page_number"], []).append(s["summary"])
            parts = [f"[{source_label}, S. {p}] {' '.join(texts)}" for p, texts in sorted(pages.items())]
            part = f"--- {source_label} ---\n" + "\n".join(parts)
        else:
            chunks = db.get_chunks_by_source(sid)
            if chunks:
                parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks[:20]]
                part = f"--- {source_label} ---\n" + "\n".join(parts)
            else:
                continue
        context_parts.append(part[:budget_per_source])
    return "\n\n".join(context_parts)


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

        # Build context with source numbering for citations
        context_parts: list[str] = []
        context_len = 0
        for sid in source_ids:
            chunks = db.get_chunks_by_source(sid)
            qnum = source_map.get(str(sid), {}).get("number", 1)
            for chunk in chunks:
                part = f"[Q{qnum}, S. {chunk['page_number']}]\n{chunk['content']}"
                if context_len + len(part) > 15000:
                    break
                context_parts.append(part)
                context_len += len(part)

        if not context_parts:
            db.update_ki_tutor_datentabelle(datentabelle_id, "failed", error="Keine Chunks vorhanden")
            return

        context = "\n\n---\n\n".join(context_parts)
        source_legend = "\n".join(
            f"[Q{info['number']}] = {info['filename']}"
            for info in sorted(source_map.values(), key=lambda x: x["number"])
        )

        client, model, _ = _get_llm_client()
        messages = [
            {"role": "system", "content": TUTOR_DATENTABELLE_PROMPT},
            {"role": "user", "content": (
                f"Quellen:\n{source_legend}\n\n"
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

Für jeden Begriff gib EXAKT dieses JSON-Format zurück (als JSON-Array):
[
  {
    "term_de": "Deutscher Fachbegriff",
    "term_en": "English translation",
    "definition": "Kurze Definition auf Deutsch (1-2 Sätze)",
    "example_sentence": "Ein Beispielsatz aus dem Text, der den Begriff verwendet",
    "page_number": 5
  }
]

Regeln:
- Extrahiere 10-20 Fachbegriffe (die wichtigsten und häufigsten)
- Nur echte Fachbegriffe, keine allgemeinen Wörter
- Definition muss präzise und verständlich sein (B1-B2 Niveau)
- example_sentence muss ein echter Satz aus dem gegebenen Text sein
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

        # Gather chunks from all selected sources
        all_chunks: list[dict] = []
        for sid in source_ids:
            all_chunks.extend(db.get_chunks_by_source(sid))
        if not all_chunks:
            logger.warning("KI Tutor: glossary generation — no chunks found")
            return

        # Build context (max ~12000 chars)
        context_parts: list[str] = []
        context_len = 0
        for chunk in all_chunks:
            part = f"[S. {chunk['page_number']}]\n{chunk['content']}"
            if context_len + len(part) > 12000:
                break
            context_parts.append(part)
            context_len += len(part)
        context = "\n\n---\n\n".join(context_parts)

        client, model, _ = _get_llm_client()
        messages = [
            {"role": "system", "content": _GLOSSARY_PROMPT},
            {"role": "user", "content": f"Extrahiere Fachbegriffe aus folgendem Text:\n\n{context}"},
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

        # Delete old glossary for these sources, then create new
        for sid in source_ids:
            db.delete_ki_tutor_glossary(sid)

        db.bulk_create_glossary_entries(source_ids[0], entries_raw)
        logger.info("KI Tutor: glossary generated ({} entries) for module {}", len(entries_raw), module_id)

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
    from src.tool_prompts import TUTOR_LERNKARTEN_PROMPT

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

            if tool in ("lernkarten", "karteikarten"):
                items = [
                    {"front": e["term_de"], "back": f"{e['term_en']} — {e['definition']}",
                     "source_label": e.get("filename", ""), "page_number": e.get("page_number")}
                    for e in selected
                ]
                title = ", ".join(e["term_de"] for e in selected[:3]) + ("…" if len(selected) > 3 else "")
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
                        "- ___ als Lücken-Platzhalter\n- Antworte NUR mit dem JSON-Array"
                    )},
                    {"role": "user", "content": f"Erstelle Lückentext-Übungen:\n\n{terms_text}"},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                exercises = _json.loads(answer)
                items = [
                    {"front": ex["sentence"], "back": ex["answer"], "options": ex["options"],
                     "correct_idx": ex["correct_idx"],
                     "source_label": next((e.get("filename", "") for e in selected if e["term_de"] == ex.get("term_de")), ""),
                     "page_number": ex.get("page_number")}
                    for ex in exercises
                ]
                title = ", ".join(e["term_de"] for e in selected[:3]) + ("…" if len(selected) > 3 else "")
            elif tool == "vokabeltest":
                terms_text = "\n".join(f"- {e['term_de']} ({e['term_en']}): {e['definition']}" for e in selected)
                messages = [
                    {"role": "system", "content": (
                        "Du erstellst Vokabeltest-Fragen (Multiple Choice).\n\n"
                        "Antworte NUR mit einem JSON-Array:\n"
                        '[{"question": "Was ist die englische Übersetzung von Normalisierung?", '
                        '"options": ["Indexing", "Normalization", "Partitioning", "Denormalization"], '
                        '"correct_idx": 1, "explanation": "Normalization ist...", '
                        '"term_de": "Normalisierung", "page_number": 12}]\n\n'
                        "Regeln:\n- Mische DE→EN, EN→DE, Definitionsfragen\n"
                        "- Genau 4 Optionen, eine korrekt\n- correct_idx = 0-3\n"
                        "- Antworte NUR mit dem JSON-Array"
                    )},
                    {"role": "user", "content": f"Erstelle Vokabeltest-Fragen:\n\n{terms_text}"},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                questions = _json.loads(answer)
                items = [
                    {"front": q["question"], "back": q["options"][q["correct_idx"]], "options": q["options"],
                     "correct_idx": q["correct_idx"], "explanation": q.get("explanation"),
                     "source_label": next((e.get("filename", "") for e in selected if e["term_de"] == q.get("term_de")), ""),
                     "page_number": q.get("page_number")}
                    for q in questions
                ]
                title = ", ".join(e["term_de"] for e in selected[:3]) + ("…" if len(selected) > 3 else "")

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
            for suuid in uuids:
                source = db.get_ki_tutor_source(suuid)
                if not source:
                    continue
                source_label = source["filename"]
                if not first_label:
                    first_label = source_label
                summaries = db.get_paragraph_summaries_by_source(source["id"])
                if summaries:
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

            # Fair budget split per source (64k total, whole lines only)
            budget_per_source = 64000 // len(context_parts)
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

            if tool in ("lernkarten", "karteikarten"):
                prompt = TUTOR_LERNKARTEN_PROMPT.replace("{count}", str(count))
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Erstelle Lernkarten aus {source_hint}:\n\n{context}"},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                data = _json.loads(answer)
                items = [
                    {"front": c["front"], "back": c["back"],
                     "source_label": c.get("source_label", first_label), "page_number": c.get("page_number"),
                     "start_time": _time_map.get((c.get("source_label", first_label), c.get("page_number", 0)))}
                    for c in data.get("cards", [])
                ]
                title = data.get("title", multi_label)
            else:
                tool_prompt = "Du erstellst Übungen basierend auf dem gegebenen Quelltext.\n\n"
                if tool == "lueckentext":
                    tool_prompt += (
                        "Erstelle Lückentext-Übungen. Antworte NUR mit einem JSON-Array:\n"
                        '[{"sentence": "Satz mit ___ als Lücke", "answer": "Antwort", '
                        '"options": ["A", "B", "C", "D"], "correct_idx": 0, '
                        '"source_label": "Dateiname", "page_number": 5}]\n'
                        f"Erstelle genau {count} Übungen."
                    )
                elif tool == "quiz":
                    tool_prompt += (
                        "Erstelle Multiple-Choice Verständnisfragen zum gegebenen Text. "
                        "Die Fragen sollen das Verständnis des Inhalts prüfen.\n\n"
                        "Antworte NUR mit einem JSON-Array:\n"
                        '[{"question": "Verständnisfrage?", "options": ["A", "B", "C", "D"], '
                        '"correct_idx": 0, "explanation": "Kurze Erklärung warum diese Antwort richtig ist", '
                        '"source_label": "Dateiname", "page_number": 5}]\n'
                        f"Erstelle genau {count} Fragen. Mische leichte und schwierige Fragen."
                    )
                else:
                    tool_prompt += (
                        "Erstelle Multiple-Choice Vokabeltest-Fragen. Antworte NUR mit einem JSON-Array:\n"
                        '[{"question": "Frage?", "options": ["A", "B", "C", "D"], '
                        '"correct_idx": 0, "explanation": "Erklärung", '
                        '"source_label": "Dateiname", "page_number": 5}]\n'
                        f"Erstelle genau {count} Fragen."
                    )
                messages = [
                    {"role": "system", "content": tool_prompt},
                    {"role": "user", "content": f"Quellen:\n\n{context}"},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                exercises = _json.loads(answer)
                if tool == "lueckentext":
                    items = [
                        {"front": ex["sentence"], "back": ex["answer"], "options": ex["options"],
                         "correct_idx": ex["correct_idx"],
                         "source_label": ex.get("source_label", first_label), "page_number": ex.get("page_number"),
                         "start_time": _time_map.get((ex.get("source_label", first_label), ex.get("page_number", 0)))}
                        for ex in exercises
                    ]
                else:  # quiz + vokabeltest
                    items = [
                        {"front": q["question"], "back": q["options"][q["correct_idx"]], "options": q["options"],
                         "correct_idx": q["correct_idx"], "explanation": q.get("explanation"),
                         "source_label": q.get("source_label", first_label), "page_number": q.get("page_number"),
                         "start_time": _time_map.get((q.get("source_label", first_label), q.get("page_number", 0)))}
                        for q in exercises
                    ]
                title = multi_label

        if not items:
            db.fail_exercise_set(set_id)
            return

        db.finalize_exercise_set(set_id, title, items)
        logger.info("KI Tutor: exercise set {} generated ({} items)", set_id, len(items))

    except Exception as e:
        logger.error("KI Tutor: exercise set {} generation failed: {}", set_id, e)
        db.fail_exercise_set(set_id)
