"""KI-Assistent Celery tasks — glossary generation."""

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

from src.features.ki_assistent.tasks._helpers import (
    _format_ts,
    _save_ki_tutor_output,
    _detect_language,
    _parse_numbered_summaries,
    _clean_summary,
    _call_llm_with_retry,
    _summarize_page,
    _summarize_batch,
    _get_llm_client,
    _clean_llm_json,
)

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

