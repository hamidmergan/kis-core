# Citation Grounding — Design

**Date:** 2026-06-01
**Status:** Approved design, pending implementation plan
**Area:** `backend` — AI Assistant RAG chat citations
**Branch:** `feat/aia-citation-grounding`

## 1. Problem

A manual audit of a 6-source workspace ("Wiss. Seminar": 3 videos, 3 PDFs) with the
prompt *"fasse zusammen"* produced an answer with 15 citation chips. Checking each chip
against the source it points to:

- **7 exact** — chip anchors the precise sentence/segment.
- **4 imprecise** — right source, but the chip lands at a *section opener* instead of the
  cited sentence (e.g. `[1] 12:48` opens "Prüfungsleistung" but the presentation-dates
  claim is at 09:28; `[2] 43:07`, `[2] 36:04`, `[3] 13:05` similar).
- **4 wrong** — chip points somewhere the claim is not:
  - `[2] 00:01` (twice) → the video's greeting/intro; the real content is at 02:59 / 09:41.
  - `[3] 20:59` → IEEE page-numbers; the "roter Faden / Gliederung" claim is at ~02:04.
  - `[4] S. 13` → "Literaturrecherche" overview; the Zotero/Citavi claim is on **page 15**.

Separately, **many bullets carry no chip at all** — so the answer does not deliver
"one source per bullet."

## 2. Root causes (verified in code)

1. **Position is chunk-level, not sentence-level.** `_resolve_citation_pages`
   (`backend/src/features/ai_assistant/routes/_helpers.py:247`) grounds a citation to the
   matched chunk's `start_time` / `page_number`. Media chunks **merge multiple Whisper
   segments** (`aia_chunker.segments_to_chunks`), so the timestamp is the *chunk's* start
   (e.g. 00:01) regardless of where in the chunk the sentence is.
2. **The resolver trusts the model's typed page when the keyword fails to match.** Rule 3
   keeps a model-typed PDF page if it is a *real* page, even when the keyword was never
   found there. The model typed `S. 13`, the paraphrased keyword
   ("Literaturverwaltungssoftware" vs. source "Literaturdatenbank/-verwaltung … Zotero,
   Citavi") failed Rule 2, so the wrong-but-valid page 13 survived.
3. **Unverifiable citations are dropped (Rule 4), and the model under-cites.** Bullets lose
   their chip either because the model never emitted one, or because the resolver deleted an
   unmatched one. The system prompt *requires* one citation per bullet
   (`backend/src/tool_prompts.py:172`); compliance is imperfect, especially on the 8B tier.

## 3. Goal & constraints

- **Coverage:** every *groundable* bullet/sentence/table-row carries a chip.
- **Accuracy:** every chip anchors the precise segment (media) or page (PDF) of its claim.
- **Phased:** Phase 1 = coverage; Phase 2 = accuracy.
- **Hard constraints (project):** deterministic and identical across model tiers (8B → cloud),
  language-agnostic (no per-language word lists), no re-ingestion of existing sources.

## 4. Approach (chosen: "A — resolver + fine-grained locators")

Build on the existing post-stream resolver. Use position-bearing data **already persisted**
at ingestion; no new ingestion step, no schema migration for Phase 1/2.

Rejected alternatives:
- **B — second LLM grounding call:** non-deterministic, adds latency/load (worse on 8B), and
  still needs deterministic position validation afterwards. Kept only as a possible future
  fallback for low-confidence lines.
- **C — sentence/segment-level re-chunking at ingestion:** cleanest long-term, but requires
  re-ingesting every source and re-tuning retrieval. Out of scope; revisit only if A's match
  precision proves insufficient.

## 5. Architecture

All work happens post-stream, at the existing call site of `_resolve_citation_pages`.

### 5.1 Matching units (where positions come from)

- **PDF / docx / pptx:** the existing chunks. They already carry `page_number` + content and
  are **per page** (`aia_chunker._extract_pdf` appends one `page_number` per chunk), so the
  page is exact once the right chunk is hit.
- **Media (audio/video):** additionally parse the persisted source VTT
  (`<base>_transcript.<lang>.vtt`) into segments `{start_time, end_time, text}`. This is the
  sub-chunk resolution that makes "green" possible. The VTT for the **displayed** language
  layer is used so the keyword anchors against what the viewer renders
  (see `citation-highlight-plain-anchor`).

### 5.2 Shared matcher (new deterministic helper)

Input: a query string (keyword or full bullet) + a source's matching units. Steps:

1. Normalize via existing `_norm_for_match`.
2. **Exact normalized substring** first (today's behaviour) → `match_type = exact`.
3. Else **token-overlap fuzzy** (e.g. Jaccard / containment over word sets) across the
   source's units; best above a threshold wins → `match_type = fuzzy`.
4. **Uniqueness check:** a fuzzy hit only counts if the best score is *clearly* ahead of the
   second-best (margin); otherwise it is treated as no confident match.

Returns `(unit, score, match_type)`. Purely lexical — no embeddings, language-agnostic,
identical on every tier.

### 5.3 Match-type tracking

Each citation carries an internal `match_type ∈ {exact, fuzzy, filled}` from emission through
to the frontend, driving the trust cue in §6.3.

## 6. Behaviour

### 6.1 Phase 2 — accuracy (green re-grounding of model citations)

For each model-emitted `[N, pos | kw]`:

- **Source-N prior:** match the keyword **only within source N's units** (never silently
  re-attribute a model citation to a different source).
- **Media:** if the keyword matches, drill into source N's **VTT segments** and use the
  matching *segment's* `start_time` instead of the chunk's. Fixes 00:01 fallbacks and
  section-opener anchors.
- **PDF:** fuzzy-match across source N's page-chunks so paraphrased keywords still find the
  real page. **Demote the model-typed page:** if any unit matches, that page wins; the typed
  page is only a last-resort fallback (image/blank pages with no extractable text).
- **Disambiguation** (keyword occurs in several units): prefer the unit **nearest the model's
  typed position** — the model's hint is a tie-breaker, not the source of truth.
- If only a low-confidence fuzzy match exists, keep the citation at the coarser-but-safe
  position and tag it `fuzzy`.

### 6.2 Phase 1 — coverage (fill bullets with no chip)

Run after re-grounding, fill only the gaps:

1. **Classify lines.** Walk the answer markdown. A line is *citable* if it is a leaf bullet,
   a standalone sentence/paragraph, or a table data row, and is **not**: a heading, an
   intro/parent line ending in `:`, or inside the closing `## Zusammenfassung` / `## Summary`
   block.
2. **Skip lines that already have a surviving citation.**
3. **For each gap line:** run the matcher over the units of **all active sources**, take the
   global best.
   - Score ≥ threshold (with the §5.2 uniqueness margin) → append `[N, pos | kw]`; position is
     the matched unit's; `kw` is a short verbatim snippet from that unit; `match_type = filled`.
     (PDF page is already exact; media reaches segment precision once §6.1's VTT drill-down
     ships in Phase 2 — until then a filled media chip is anchored at chunk granularity.)
   - Below threshold → **leave the line uncited.** Forcing a weak source is worse than a
     missing chip; in practice only genuine model self-synthesis (which the prompt already
     asks to omit) ends up uncited.

### 6.3 Trust cue (frontend)

- `exact` → chip exactly as today (solid, fully trustworthy = precise spot).
- `fuzzy` / `filled` → **same colour and size**, but a **dotted underline + tooltip
  "ungefähre Stelle"**. No `~` prefix, no extra colour/icon. Subtle, but visible on a skim —
  resolves the audit's "everything looks equally confident" trust problem without clutter.

### 6.4 Post-stream pipeline order

"Phase 1 / Phase 2" are **delivery increments**, not runtime stages. At runtime, once both
ship, the post-stream steps run in this order:

1. `_sanitize_citations` — repair `[N] pos` → `[N, pos]` (existing).
2. **Green re-ground** model citations (§6.1) — replaces today's Rule 2/3 position logic.
3. **Coverage fill** gaps (§6.2) — emits green/`filled` positions.
4. `_strip_summary_citations` — strip the closing summary block (existing).

### 6.5 Performance

A source is cited many times per answer. Parse VTT / load a source's units **once per
request** (small cache keyed by source id). Matching is lexical and bounded by
`lines × units`, which is small for chat answers.

## 7. Testing

- **Eval harness from the audit table.** Encode the 15 audited
  `(source, position, claim, verdict)` triples as ground truth; assert the new pipeline moves
  "4 wrong / 4 imprecise" toward exact. Doubles as a regression guard.
- **Unit tests** for the matcher (exact / fuzzy / no-match, uniqueness margin, source-N prior)
  and the line classifier (bullet vs. heading vs. `:`-intro vs. summary vs. table row).
- **Threshold calibration** against the eval set — chosen from data, not guessed.

## 8. Non-goals (YAGNI)

- No re-ingestion or chunk-schema change (that is Approach C, deferred).
- No second LLM call (Approach B, deferred).
- No per-segment embeddings — lexical matching only for now.
- No new chip colours/icons beyond the dotted-underline cue.

## 9. Open risks

- **Fuzzy precision on a repetitive corpus** (the same topics recur across VL1/VL2/VL3 and the
  PDFs) is the make-or-break. Mitigated by the source-N prior (§6.1) and the uniqueness margin
  (§5.2); validated by the eval harness (§7).
- **Threshold sensitivity** to bullet/segment length — calibrated, not constant-set.
- **Keyword language layer** must match the displayed transcript layer (DE vs. EN) or the
  plain-text highlight anchor misses (§5.1).
