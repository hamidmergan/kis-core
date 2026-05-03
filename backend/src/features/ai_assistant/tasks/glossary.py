"""KI-Assistent Celery tasks - glossary generation."""

import concurrent.futures
import os
import re

from langfuse.decorators import langfuse_context, observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import open_input_file
from src.limits import (
    AIA_SUMMARY_MAX_RETRIES,
    AIA_SUMMARY_TIMEOUT_SMALL,
    AIA_SUMMARY_TIMEOUT_LARGE,
    AIA_SUMMARY_MAX_TOKENS_SMALL,
    AIA_SUMMARY_MAX_TOKENS_LARGE,
    AIA_SUMMARY_MAX_TOKENS_BATCH,
    AIA_SUMMARY_CONTENT_MAX_CHARS,
    AIA_SUMMARY_PARALLEL_WORKERS_SMALL,
    AIA_SUMMARY_PARALLEL_WORKERS_LARGE,
    AIA_SUMMARY_BATCH_SIZE,
)
from src.features.ai_assistant.tasks._helpers import (
    _get_llm_client,
    _clean_llm_json,
)

_GLOSSARY_PROMPT = """You are a technical-terminology expert. Extract the most important technical terms from the following text.

Text fragments are marked with source citations: [Q1, S. 5] = source 1, page 5.

For every term return EXACTLY this JSON format (as a JSON array):
[
  {
    "term_de": "Technical term in the source language",
    "term_en": "Translation (see rules)",
    "definition": "Short explanation in German (B1 level, 1-2 sentences)",
    "definition_en": "Short explanation in English (B1 level, 1-2 sentences)",
    "example_sentence": "A sentence from the text that uses the term (source language)",
    "example_sentence_en": "English translation of the example sentence",
    "source_label": "Q1",
    "page_number": 5
  }
]

Rules:
- Extract exactly 5 technical terms (the most important and frequent ones)
- Only true technical terms, no general words
- CRITICAL for term_de: the term must appear VERBATIM as a contiguous word or phrase in the text. If the text says "in den deutschen Arbeitsmarkt zu integrieren", you may NOT turn that into "Arbeitsmarktintegration". Take "Arbeitsmarkt" instead, or skip it. Do NOT invent compounds or nominalizations that are not exactly in the text.
- term_en: if the source text is NOT English, translate the term to English. If the source text is English, translate the term to German. Never the same language as term_de.
- definition: simple explanation in German, understandable at B1 level
- definition_en: simple explanation in English, understandable at B1 level
- example_sentence: a sentence from the given text that uses the term
- example_sentence_en: English translation of that sentence
- source_label: the source citation (Q1, Q2, ...) the term comes from
- page_number: the page number where the term appears
- Respond ONLY with the JSON array, no other text."""


@celery_app.task(bind=True, name="aia.generate_glossary", queue="aia",
                 soft_time_limit=120, time_limit=180)
@observe(name="aia-glossary")
def run_generate_glossary(self, workspace_id: int, source_ids: list[int]):
    """Generate glossary entries from source chunks as a background job."""
    import json as _json

    try:
        logger.info("KI Tutor: generating glossary for workspace {} sources {}", workspace_id, source_ids)

        # Gather chunks from all selected sources, track which source each chunk belongs to
        all_chunks: list[dict] = []
        for sid in source_ids:
            chunks = db.get_chunks_by_source(sid)
            for c in chunks:
                c["_source_id"] = sid
            all_chunks.extend(chunks)
        if not all_chunks:
            logger.warning("KI Tutor: glossary generation - no chunks found")
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
        existing = db.get_aia_glossary_by_workspace(workspace_id)
        existing_terms_list = [e["term_de"] for e in existing]
        exclude_hint = ""
        if existing_terms_list:
            exclude_hint = f"\n\nFolgende Begriffe existieren bereits - überspringe diese: {', '.join(existing_terms_list)}"

        client, model, _ = _get_llm_client()
        messages = [
            {"role": "system", "content": _GLOSSARY_PROMPT},
            {"role": "user", "content": f"Extrahiere Fachbegriffe aus folgendem Text:\n\n{context}{exclude_hint}"},
        ]

        response = client.chat.completions.create(model=model, messages=messages, temperature=0.1)
        raw = response.choices[0].message.content
        if not raw:
            logger.error("KI Tutor: glossary generation - LLM returned empty content")
            return

        entries_raw = _json.loads(_clean_llm_json(raw))
        if not isinstance(entries_raw, list):
            logger.error("KI Tutor: glossary generation - expected JSON array")
            return

        # Validate: term must appear verbatim in source text
        context_lower = context.lower()
        entries_raw = [e for e in entries_raw if e.get("term_de", "").strip().lower() in context_lower]

        # Deduplicate: skip terms that already exist
        existing = db.get_aia_glossary_by_workspace(workspace_id)
        existing_terms = {e["term_de"].strip().lower() for e in existing}
        new_entries = [e for e in entries_raw if e.get("term_de", "").strip().lower() not in existing_terms]

        # Respect overall limit of 150 and cap at 5 new entries per run
        remaining_slots = 150 - len(existing)
        if remaining_slots <= 0:
            logger.info("KI Tutor: glossary limit reached for workspace {}, skipping", workspace_id)
            return
        new_entries = new_entries[:min(5, remaining_slots)]

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
        logger.info("KI Tutor: glossary added {} new entries (skipped {} duplicates) for workspace {}",
                     len(new_entries), len(entries_raw) - len(new_entries), workspace_id)

    except Exception as e:
        logger.error("KI Tutor: glossary generation failed for workspace {}: {}", workspace_id, e)


# ── Exercise Set generation (replaces threading.Thread) ──────────────────────

