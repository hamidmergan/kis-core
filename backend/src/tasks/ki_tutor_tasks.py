"""Celery tasks for KI Tutor – indexing source documents."""

import concurrent.futures
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
    summary = _clean_summary(resp.choices[0].message.content or "")
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
    content = resp.choices[0].message.content or ""
    # Strip <think> blocks (some models ignore think=False)
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    # Unclosed <think> — keep only what's before it
    if "<think>" in content:
        content = content[:content.index("<think>")].strip()
    summaries = _parse_numbered_summaries(content, n)
    for i, (p, s) in enumerate(zip(pages_batch, summaries)):
        logger.debug("KI Tutor: batch page {} summary: {!r}", p["page_number"], s[:300])
    return summaries


@celery_app.task(bind=True, name="ki_tutor.index_source", queue="general")
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
            # 5. Extract chunks
            from src.services import ki_tutor_chunker
            chunks = ki_tutor_chunker.extract_chunks(local_path, file_type)

            # 6. Save chunks to DB
            chunk_ids: list[int] = []
            for chunk in chunks:
                chunk_id = db.create_ki_tutor_chunk(
                    source_id=source_id,
                    page_number=chunk["page_number"],
                    content=chunk["content"],
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


@celery_app.task(bind=True, name="ki_tutor.generate_summaries", queue="general")
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


@celery_app.task(bind=True, name="ki_tutor.generate_mindmap", queue="general",
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

        # Fair budget split per source
        budget_per_source = 16000 // len(source_ids)
        trimmed_parts = [p[:budget_per_source] for p in context_parts]
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

        raw = response.choices[0].message.content
        if not raw:
            db.update_ki_tutor_mindmap(mindmap_id, "failed", error="LLM returned empty content")
            return

        answer = raw.strip()
        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        mindmap = _json.loads(answer)
        if not isinstance(mindmap, dict) or "topic" not in mindmap:
            db.update_ki_tutor_mindmap(mindmap_id, "failed", error="Invalid mindmap format")
            return

        db.update_ki_tutor_mindmap(mindmap_id, "success", mindmap=mindmap)
        logger.info("KI Tutor: mindmap {} generated successfully", mindmap_id)

    except Exception as e:
        logger.error("KI Tutor: mindmap {} generation failed: {}", mindmap_id, e)
        db.update_ki_tutor_mindmap(mindmap_id, "failed", error=str(e))
