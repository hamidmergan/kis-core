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
    """Parse '1. summary\\n2. summary\\n...' format."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    result = []
    for line in lines:
        m = re.match(r"^\d+[\.)]\s*(.+)$", line)
        if m:
            result.append(m.group(1).strip())
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


_SUMMARY_SYSTEM = (
    "You are a study assistant writing margin notes for a university PDF reader sidebar.\n"
    "Each paragraph gets exactly ONE note that helps a student grasp the point without reading the full text.\n\n"
    "Rules:\n"
    "- State what the paragraph CLAIMS or SHOWS — always use a verb. Then add the most specific detail "
    "(number, comparison, name, finding).\n"
    "- Every note must be a complete thought. NEVER write keyword-only lists.\n"
    "- Specificity test: if your note could apply to a different paragraph on the same topic, add the "
    "distinguishing detail.\n"
    "- Length: 1-2 sentences, max 280 characters. Abbreviations OK.\n"
    "- Keep numbers, names, abbreviations exactly as in the source.\n"
    "- Tables: summarize the WHOLE table in one note, not each row.\n"
    "- Skip filler (headers only, page numbers, TOC, footnotes, captions) — write SKIP.\n"
    "- Write in {lang}.\n\n"
    "BAD (keyword list, no verb, too generic):\n"
    "  'Integration, Qualifizierung, MINT-Defizit'\n"
    "BAD (could apply to any paragraph about the topic):\n"
    "  'Herausforderungen internationaler Studierender werden beschrieben'\n\n"
    "GOOD examples by paragraph type:\n"
    "- Data/evidence: 'Abbruchquote int. Studierender liegt bei 49 % vs. 27 % dt. (Bachelor). "
    "65 % wollen in DE bleiben, tatsächlich schaffen es weniger als 50 %.'\n"
    "- Claim/argument: 'KIS-Projekt setzt KI und Digitalisierung ein, um Lehre für int. Gruppen "
    "zu verbessern und Studienerfolgsquote zu erhöhen.'\n"
    "- Definition: 'Formatives Assessment = bewertungsfreie Lernstandserhebung während des Semesters, "
    "Gegensatz zu summativ (Klausur).'\n"
    "- Methodology: 'Mixed-Methods-Design: Online-Befragung (n=1200) + 15 Leitfadeninterviews, "
    "Auswertung nach Mayring.'\n\n"
    "Output format: one note per line, prefixed with the paragraph number.\n"
    "1. KI-Tutor an TH Lübeck unterstützt int. Studierende ab Pilot WS 2024 mit KI-gestützter Lehre.\n"
    "2. SKIP\n"
    "3. Abbruchquote int. Studierender liegt bei 49 % vs. 27 % dt. Hauptursachen: Finanzen, "
    "Sprache, fehlende Netzwerke, Admin-Hürden.\n"
    "4. Innovationsgrad wird nach drei Kriterien bewertet: Neuheit, Transformativität und Adaptivität.\n\n"
    "Self-check before output: Does each note contain a verb? Does it mention something specific? "
    "Could a student understand the paragraph's point from this note alone?\n"
    "Do not add any other text."
)

@celery_app.task(bind=True, name="ki_tutor.generate_summaries", queue="general")
def run_generate_summaries(self, source_uuid: str):
    """Generate AI paragraph summaries for a PDF source."""
    try:
        source = db.get_ki_tutor_source(source_uuid)
        if source is None:
            raise RuntimeError(f"Source not found: {source_uuid}")

        if source["file_type"] != "pdf":
            return

        db.update_ki_tutor_source_summaries_status(source_uuid, "generating")
        logger.info("KI Tutor: generating summaries for source {}", source_uuid)

        # 1. Extract paragraphs with bounding boxes
        import os
        suffix = os.path.splitext(source["filename"])[1] or ".pdf"
        with open_input_file(source["file_path"], suffix=suffix) as local_path:
            from src.services.ki_tutor_chunker import extract_paragraphs_with_bbox
            paragraphs = extract_paragraphs_with_bbox(local_path)

        if not paragraphs:
            db.update_ki_tutor_source_summaries_status(source_uuid, "ready")
            logger.info("KI Tutor: no paragraphs found for {}", source_uuid)
            return

        # 2. Detect language
        sample = " ".join(p["content"][:200] for p in paragraphs[:3])
        lang = _detect_language(sample)

        # 3. Build LLM client
        from langfuse.openai import OpenAI
        from src.config import Settings
        s = Settings()
        client = OpenAI(api_key=s.effective_llm_api_key, base_url=s.effective_llm_base_url, max_retries=0, timeout=30)
        model = s.effective_llm_model
        extra_body = {"think": False} if s.llm_provider == "ollama" else {}

        # 4. Generate summaries in batches (with retry on rate limit)
        import time as _time
        # Ollama local: larger batches → fewer LLM calls → faster overall
        _BATCH = 10 if s.llm_provider == "ollama" else 5
        # Ollama needs more timeout (slow local hardware); KISSKI is fast
        _TIMEOUT = 120 if s.llm_provider == "ollama" else 30
        _MAX_RETRIES = 3
        all_summaries: list[str] = []
        for i in range(0, len(paragraphs), _BATCH):
            batch = paragraphs[i:i + _BATCH]
            user_parts = []
            for j, p in enumerate(batch, 1):
                user_parts.append(f"{j}. {p['content'][:2500]}")

            for attempt in range(_MAX_RETRIES):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": _SUMMARY_SYSTEM.format(lang=lang)},
                            {"role": "user", "content": "\n\n".join(user_parts)},
                        ],
                        temperature=0.1,
                        max_tokens=_BATCH * 250,
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

            answer = response.choices[0].message.content or ""
            batch_summaries = _parse_numbered_summaries(answer, len(batch))
            all_summaries.extend(batch_summaries)
            logger.info(
                "KI Tutor: summarized paragraphs {}-{}/{} for source {}",
                i + 1, i + len(batch), len(paragraphs), source_uuid,
            )

        # 4b. Retry empty summaries individually
        _MIN_RETRY_WORDS = 15
        for idx, (summ, par) in enumerate(zip(all_summaries, paragraphs)):
            if summ.strip() and summ.strip().upper() != "SKIP":
                continue
            if len(par["content"].split()) < _MIN_RETRY_WORDS:
                continue
            logger.info("KI Tutor: retrying empty summary for paragraph {} (p{})", idx, par["page_number"])
            try:
                retry_resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": _SUMMARY_SYSTEM.format(lang=lang)},
                        {"role": "user", "content": f"1. {par['content'][:2500]}"},
                    ],
                    temperature=0.1,
                    max_tokens=300,
                    timeout=_TIMEOUT,
                    extra_body=extra_body or None,
                )
                retry_text = retry_resp.choices[0].message.content or ""
                retry_parsed = _parse_numbered_summaries(retry_text, 1)
                if retry_parsed[0].strip() and retry_parsed[0].strip().upper() != "SKIP":
                    all_summaries[idx] = retry_parsed[0]
                    logger.info("KI Tutor: retry succeeded for paragraph {}: {!r}", idx, retry_parsed[0][:80])
            except Exception:
                logger.warning("KI Tutor: retry failed for paragraph {}", idx)

        # 5. Save summaries to DB
        db.bulk_create_paragraph_summaries(
            source_id=source["id"],
            summaries=[
                {
                    "page_number": p["page_number"],
                    "block_index": p["block_index"],
                    "bbox": p["bbox"],
                    "content": p["content"],
                    "summary": s,
                }
                for p, s in zip(paragraphs, all_summaries)
            ],
        )

        # 6. Done
        db.update_ki_tutor_source_summaries_status(source_uuid, "ready")
        logger.info("KI Tutor: summaries ready for source {} ({} paragraphs)", source_uuid, len(paragraphs))

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "rate" in err_str.lower():
            status = "rate_limited"
        else:
            status = "failed"
        logger.error("KI Tutor: summary generation {} for {}: {}", status, source_uuid, e)
        db.update_ki_tutor_source_summaries_status(source_uuid, status)
