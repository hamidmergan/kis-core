"""Celery tasks for KI Tutor – indexing source documents."""

import re

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import open_input_file


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


from src.tool_prompts import (
    TUTOR_SUMMARY_PAGE_SYSTEM_SMALL as _SUMMARY_SYSTEM_SMALL,
    TUTOR_SUMMARY_PAGE_USER_SMALL as _SUMMARY_USER_SMALL,
    TUTOR_SUMMARY_PAGE_SYSTEM_LARGE as _SUMMARY_SYSTEM_LARGE,
    TUTOR_SUMMARY_PAGE_USER_LARGE as _SUMMARY_USER_LARGE,
)

@celery_app.task(bind=True, name="ki_tutor.generate_summaries", queue="general")
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

        # 3. Build LLM client + select prompt by provider
        from langfuse.openai import OpenAI
        from src.config import Settings
        s = Settings()
        client = OpenAI(api_key=s.effective_llm_api_key, base_url=s.effective_llm_base_url, max_retries=0, timeout=90)
        model = s.effective_llm_model
        is_small = s.llm_provider == "ollama"
        extra_body = {"think": False} if is_small else {}

        # 4. Generate summaries — one page per request for reliable output
        import time as _time
        _TIMEOUT = 120 if is_small else 90
        _MAX_RETRIES = 3
        all_summaries: list[str] = []
        for i, p in enumerate(pages):
            if is_small:
                sys_msg = _SUMMARY_SYSTEM_SMALL
                user_msg = _SUMMARY_USER_SMALL.format(lang=lang, content=p["content"][:3000])
            else:
                sys_msg = _SUMMARY_SYSTEM_LARGE.format(lang=lang)
                user_msg = _SUMMARY_USER_LARGE.format(content=p["content"][:3000])

            for attempt in range(_MAX_RETRIES):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": sys_msg},
                            {"role": "user", "content": user_msg},
                        ],
                        temperature=0.1,
                        max_tokens=2048 if is_small else 512,
                        timeout=_TIMEOUT,
                        extra_body=extra_body or None,
                    )
                    break
                except Exception as api_err:
                    err_str = str(api_err)
                    if ("429" in err_str or "timeout" in err_str.lower()) and attempt < _MAX_RETRIES - 1:
                        wait = 30 * (attempt + 1)
                        logger.warning("KI Tutor: rate limited/timeout, retrying in {}s (attempt {}/{})...", wait, attempt + 1, _MAX_RETRIES)
                        _time.sleep(wait)
                    else:
                        raise

            answer = (response.choices[0].message.content or "").strip()
            # Strip <think> blocks that qwen3 may emit despite think=False
            answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
            # Strip leading number prefix if model echoes it (e.g. "1. summary")
            answer = re.sub(r"^\s*\d+[\.)]\s*", "", answer).strip()
            logger.debug("KI Tutor: page {} summary: {!r}", p["page_number"], answer[:300])
            all_summaries.append(answer)
            logger.info(
                "KI Tutor: summarized page {}/{} for source {}",
                i + 1, len(pages), source_uuid,
            )

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
                if s.strip() and s.strip().upper() != "SKIP"
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
