# AIA pgvector-only: no summaries at upload (Open-Notebook style)

**Status:** Implemented on branch `feat/aia-pgvector-only-no-summaries`. This doc records the final design + rationale (the brainstorm/test history that led here is summarized below).

## Goal

Cut KI-Tutor PDF upload from ~20–30 min toward ~3–8 min by **not generating summaries at upload**. Both chat paths answer from pgvector retrieval — SPECIFIC = hybrid search (unchanged), GENERIC = multi-query retrieval (new). Page-summaries survive as an **opt-in** sidebar feature, no longer an automatic upload cost.

## Why (test findings + product decision + external validation)

- **Tests (442-page PDF, GWDG):** upload time is structural, not tunable. Embedding is throughput-bound on the 4B model (batch 20→100 = no change). Summaries are output-decode-bound (batch 25→125 = no change, truncation risk). OCR parallelism tripped GWDG 429s (4 workers → 18/31 pages lost text). All edge-tuning reverted.
- **Product decision (owner):** GENERIC ("what is this about?") questions are rare; SPECIFIC ("explain X on p.50") is the common case. A heavy per-upload summary tax for a rare query type is the wrong optimization. A single whole-doc summary can't fit a 500-page doc (≈400k tokens > context window), so retrieval is the only fast option for large docs anyway.
- **External validation:** literature says naive pre-summarization can *hurt* retrieval; pure top-k is weak for overview, which GraphRAG / query-decomposition address. **Open Notebook** (read the actual code: `graphs/source.py`, `graphs/ask.py`) does NOT summarize at ingest — it chunks+embeds, and answers via an agentic strategy that decomposes the question into ≤5 sub-queries, runs each through vector search, and synthesizes. Our design = their architecture; the GENERIC path copies their multi-query idea.

## What was built

### 1. GENERIC chat = multi-query retrieval (`routes/chat.py`)
- New prompt `AIA_SEARCH_STRATEGY_SYSTEM` (`tool_prompts.py`) — language-agnostic; decomposes a question into 2–4 diverse sub-queries.
- New `_generate_search_strategy(llm, question)` — one small LLM call; always anchors the original question; falls back to `[question]` on error.
- New `_retrieve_generic_context(llm, provider, workspace_id, source_ids, question)` — embeds each sub-query, runs `hybrid_search_chunks` per query, merges + dedups, diversifies by source (per-source mini-search backfill, then first raw chunk), and an even-spread raw-chunk fallback when retrieval is empty.
- GENERIC branch now calls `_retrieve_generic_context`; `_assemble_generic_context` (summary-based) and `_split_doc_summary_by_markers` removed. SPECIFIC path's doc-summary fallback replaced with a raw-chunk fallback.
- Constants: `_GENERIC_MAX_QUERIES = 4`, `_GENERIC_PER_QUERY_LIMIT = 8`.

### 2. Upload stops generating summaries (`tasks/ingestion.py`)
- `run_index_source` no longer dispatches `run_generate_summaries` / `run_generate_doc_summary`. Source is `ready` straight after embedding. Sets `summaries_status="none"` + clears progress so the source card shows ready and the sidebar offers its manual "generate" button.

### 3. Tests (`tests/test_chat_paths.py`)
- Replaced summary-assembly tests with: search-strategy parsing/fallback, multi-query merge+dedup+diversify, missing-source backfill, raw-chunk fallback. **253 passed.**

## What was deliberately NOT done (and why)

- **No deletion of the summary pipeline.** Correction to an early assumption: studio + language-training + a PDF sidebar still reference page-summaries:
  - `studio/mindmap.py` reads page-summaries, **falls back to chunks** when absent (verified). `_summarize_*` imports are vestigial.
  - `studio/data_table.py` uses chunks directly; `_summarize_*` imports vestigial.
  - `language_training/_context.py` has a `use_chunks` flag.
  - `routes/sources/_pdf.py` GET `/summaries` + POST `/summaries/generate` = a user-facing sidebar with a manual generate button (still dispatches `run_generate_summaries`).
- So page-summaries become **opt-in** (sidebar button), studio degrades to chunks, doc-summary is dead-but-dormant. Deleting would break vestigial imports + remove a working opt-in feature for marginal gain. Mirrors Open Notebook's manual "transformations".
- Rejected earlier ideas: truncate-at-100 (lossy), 1-call summary (can't fit big docs), batch/parallelism tuning (no benefit), lazy auto-summaries (still pays the tax, more pipeline).

## Known implications / follow-ups

- **PDF "summaries" sidebar is empty for new uploads** until the user clicks generate. Intended (opt-in), but the frontend copy may want a clearer empty-state ("Zusammenfassungen on-demand erzeugen").
- **Mindmap/data-table now build from chunks** (slightly different from summary-based input). Acceptable; revisit if quality drops.
- If real usage later shows GENERIC is NOT rare: blend in the cheap SAC pattern (one doc-level summary attached to chunks) — not per-page summaries. Reversible; chunks+embeddings are all stored.
- Separate (not in this branch): admin-configurable OCR on/off + page/media limits (`aia_limits()` accessor); lighter embedding model option (bge-m3/nomic) to halve embed time.

## Out of scope

- SPECIFIC retrieval path changes.
- Destructive migration dropping `aia_page_summaries` / `aia_sources.summary` (only after opt-in proves out).
