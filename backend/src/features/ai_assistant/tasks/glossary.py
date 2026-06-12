"""KI-Assistent Celery tasks - glossary generation.

Pull-based generation model
---------------------------
Entries are a workspace-shared pool keyed by (source_id, chunk_id). Each user
has a personal pick list (``aia_user_glossary_picks``). One generate-click
delivers up to ``PICKS_PER_RUN`` fresh picks for the user:

1. Grab unpicked pool entries for the user's selected sources.
2. If still short, atomically claim the next unprocessed chunk in those
   sources, LLM-extract its learnable terms, and add them to the pool.
3. Loop until the user has 10 fresh picks or no unprocessed chunks remain.

A "processed" chunk never gets a second LLM call — User B/C reuses the pool
User A built up. The flag (``aia_chunks.glossary_processed``) is set even when
the LLM returns zero terms for a chunk, so empty chunks don't get re-tried.
"""

import json

from langfuse.decorators import observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.limits import GLOSSARY_LIMIT
from src.features.ai_assistant.tasks._helpers import (
    _get_llm_client,
    _clean_llm_json,
)


PICKS_PER_RUN = 10
MAX_CHUNKS_PER_RUN = 20  # safety cap so one click can't burn through a 500-chunk doc


_GLOSSARY_CHUNK_PROMPT = """You extract learnable technical and academic terms for B1-level international students from ONE short text chunk.

Return ALL terms in this chunk that a B1 learner should learn for university study. Do not artificially cap the count — return everything genuinely useful. If the chunk is empty, generic, or contains only function words, return [].

Respond ONLY with a JSON array:
[
  {
    "term_de": "Technical/academic term in the source language",
    "term_en": "Translation (see rules)",
    "definition": "Short explanation in German (B1 level, 1-2 sentences)",
    "definition_en": "Short explanation in English (B1 level, 1-2 sentences)",
    "example_sentence": "A sentence from the chunk that uses the term",
    "example_sentence_en": "English translation of the example sentence"
  }
]

Rules:
- Two categories are allowed: (a) domain-specific technical terms, (b) academic/educational language that goes beyond A2/B1 everyday vocabulary.
- DO NOT extract: function words, trivial A1/A2 everyday words.
- CRITICAL for term_de: the term must appear VERBATIM as a contiguous word or phrase in the chunk. If the text says "in den deutschen Arbeitsmarkt zu integrieren", you may NOT turn that into "Arbeitsmarktintegration". Take "Arbeitsmarkt" or "integrieren" instead. Do NOT invent compounds or nominalizations that are not exactly in the text.
- For inflected verbs/adjectives the base form as term_de is allowed when the form is clearly recognizable (e.g. text "zu erhöhen" -> term_de "erhöhen" is fine).
- term_en: if the source text is NOT English, translate to English. If the source text IS English, translate to German. Never the same language as term_de.
- definition / definition_en: simple explanation at B1 level.
- example_sentence: a sentence from THIS chunk that uses the term.
- Respond ONLY with the JSON array."""


@celery_app.task(bind=True, name="aia.generate_glossary", queue="aia",
                 soft_time_limit=180, time_limit=240)
@observe(name="aia-glossary")
def run_generate_glossary(self, workspace_id: int, user_id: int, source_ids: list[int]):
    """Deliver up to PICKS_PER_RUN fresh glossary picks for one user. May trigger
    LLM calls on previously-unseen chunks; reuses the shared pool wherever
    possible."""
    try:
        logger.info(
            "KI Tutor: glossary pull for workspace {} user {} sources {}",
            workspace_id, user_id, source_ids,
        )
        if not source_ids:
            return

        existing_picks = db.get_user_glossary_pick_count(workspace_id, user_id)
        remaining_slots = GLOSSARY_LIMIT - existing_picks
        if remaining_slots <= 0:
            logger.info("KI Tutor: glossary limit reached for user {} in workspace {}",
                        user_id, workspace_id)
            return

        target = min(PICKS_PER_RUN, remaining_slots)
        # Accumulate picks in memory and only commit at the very end. The
        # frontend polls the glossary list every 3s and stops as soon as
        # entries.length changes — so partial writes would freeze the UI at
        # the first intermediate count (e.g. user sees 3 of 10).
        to_pick: list[int] = [e["id"] for e in db.get_unpicked_pool_entries(source_ids, user_id, target)]

        client = None
        chunks_processed = 0
        if len(to_pick) < target:
            workspace_terms = db.get_pool_terms_for_workspace(workspace_id)
            while len(to_pick) < target and chunks_processed < MAX_CHUNKS_PER_RUN:
                chunk = db.claim_next_unprocessed_chunk(source_ids)
                if not chunk:
                    logger.info("KI Tutor: glossary - no more unprocessed chunks for sources {}", source_ids)
                    break
                chunks_processed += 1

                if client is None:
                    client, model, _ = _get_llm_client()
                new_pool_ids = _extract_and_store_chunk(
                    client, model, chunk, workspace_terms,
                )
                if not new_pool_ids:
                    continue  # empty chunk — already marked processed, move on
                remaining = target - len(to_pick)
                to_pick.extend(new_pool_ids[:remaining])

        if to_pick:
            db.create_user_picks(user_id, to_pick)
        logger.info(
            "KI Tutor: glossary delivered {} picks (LLM-touched {} chunks) for user {}",
            len(to_pick), chunks_processed, user_id,
        )

    except Exception as e:
        logger.error("KI Tutor: glossary generation failed for workspace {} user {}: {}",
                     workspace_id, user_id, e)


def _extract_and_store_chunk(client, model, chunk: dict, workspace_terms: set[str]) -> list[int]:
    """Run the LLM on one chunk, persist its terms to the shared pool, return
    the new pool entry ids. ``workspace_terms`` (lowercased) is mutated in
    place so subsequent chunks in the same run skip duplicates."""
    content = chunk.get("content") or ""
    if not content.strip():
        return []

    messages = [
        {"role": "system", "content": _GLOSSARY_CHUNK_PROMPT},
        {"role": "user", "content": f"Chunk:\n\n{content}"},
    ]
    from src.features.ai_assistant.scheduling.gate_service import gate_acquire
    gate_acquire("studio")  # no-op unless aia_gate_enabled
    try:
        response = client.chat.completions.create(model=model, messages=messages, temperature=0.1)
    except Exception as e:
        logger.warning("KI Tutor: glossary LLM call failed for chunk {}: {}", chunk["id"], e)
        return []

    raw = response.choices[0].message.content or ""
    try:
        parsed = json.loads(_clean_llm_json(raw))
    except (json.JSONDecodeError, ValueError):
        logger.warning("KI Tutor: glossary LLM returned invalid JSON for chunk {}", chunk["id"])
        return []
    if not isinstance(parsed, list):
        return []

    content_lower = content.lower()
    chunk_seen: set[str] = set()
    new_entries: list[dict] = []
    for raw_entry in parsed:
        if not isinstance(raw_entry, dict):
            continue
        term = (raw_entry.get("term_de") or "").strip()
        if not term:
            continue
        term_key = term.lower()
        # Verbatim: term must appear in THIS chunk.
        if term_key not in content_lower:
            continue
        # Dedup against existing pool (workspace-wide) and within this batch.
        if term_key in workspace_terms or term_key in chunk_seen:
            continue
        chunk_seen.add(term_key)
        new_entries.append({
            "term_de": term,
            "term_en": (raw_entry.get("term_en") or "").strip(),
            "definition": (raw_entry.get("definition") or "").strip(),
            "definition_en": (raw_entry.get("definition_en") or "").strip(),
            "example_sentence": (raw_entry.get("example_sentence") or "").strip(),
            "example_sentence_en": (raw_entry.get("example_sentence_en") or "").strip(),
            "page_number": chunk.get("page_number"),
        })

    if not new_entries:
        return []

    rows = db.bulk_create_pool_entries(chunk["source_id"], chunk["id"], new_entries)
    for r in rows:
        workspace_terms.add(r["term_de"].lower())
    return [r["id"] for r in rows]
