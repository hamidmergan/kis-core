# AIA Unified Post-hoc Attribution + Highlight Removal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ALL RAG chat modes (specific / generic / scope) cite sources through ONE post-hoc pgvector path (no model citation injection), with a retrieval↔attribution cross-check, and remove citation highlighting everywhere except the manual EmbedPDF action-bar highlight.

**Architecture:** The LLM writes a plain answer (no `[N, #C | kw]` chips). After the stream, every substantial line is embedded (batched in one call), searched in pgvector, and — if the hit's page/timestamp belongs to a chunk that was actually retrieved into context (cross-check) — gets a nav-only chip `[N, S. X]` / `[N, MM:SS]`. The live grounder, chunk-id registry, keyword/offset resolvers, and span-offset geometry are deleted. Chips never carry `@start-end` or `| keyword`; clicking a chip only scrolls to the page/timestamp. The popup/action-bar exact-selection highlight stays (separate code path, not citation-derived).

**Tech Stack:** FastAPI streaming (SSE), pgvector hybrid search, OpenAI-compat embeddings (batched via `provider.embed(list)`), Next.js/React + react-markdown frontend, pytest + vitest.

---

## File Structure

**Backend — delete entirely:**
- `backend/src/features/ai_assistant/routes/_grounding.py` (live CitationGrounder)
- `backend/src/features/ai_assistant/routes/_chunk_cite.py` (resolve_chunk_refs)
- `backend/src/features/ai_assistant/routes/_page_geometry.py` (span-offset geometry)
- `backend/src/features/ai_assistant/routes/_citation_match.py` IF unused after removals (verify; media timestamp helper may need to move)

**Backend — modify:**
- `backend/src/tool_prompts.py` — drop the CITATION FORMAT block from `aia_system_rag`
- `backend/src/features/ai_assistant/routes/_helpers.py` — keep `_attribute_generic_text` (+ cross-check), `_pick_attribution`, `_attribution_chip` (nav-only), `_needs_attribution`; delete `resolve_citation_positions`, `fill_uncited_lines`, `_reground_by_line`, `_nav_only_chips`, `_strip_resolved_citation_chips`, `_append_scope_anchor`, `_highlights_enabled`, `SourceUnitLoader.offset_suffix(es)`, `with_offsets` params, offset bits of `_attribution_chip`
- `backend/src/features/ai_assistant/routes/chat.py` — replace grounder+finalize with unified post-hoc for all RAG modes; drop chunk_registry build, scope nav-only branches, `_offset_fn`, `AIA_HIGHLIGHTS` usage

**Backend — delete obsolete tests:**
`test_chunk_cite.py`, `test_citation_offsets.py`, `test_citation_resolve.py`, `test_citation_resolver.py`, `test_citation_incremental.py`, `test_citation_footer_kw.py`, `test_citation_furniture.py`, `test_citation_nav_only.py`, `test_citation_seen_pages.py`, `test_citation_title_lines.py`, `test_citation_coverage.py`, `test_citation_dedup.py`, `test_citation_lines.py`, `test_citation_units.py`, `test_citation_toc.py`, `test_toc_grounding.py`, `test_collapse_fold_ocr.py`, `test_scope_chip_strip.py`, `test_scope_nav_only.py`, `test_highlights_flag.py`, `test_nav_only_offset_skip.py`, `test_citation_id_leak.py`, `test_citation_match.py` (only if `_citation_match.py` deleted)

**Backend — keep/extend tests:** `test_generic_attribution.py` (rename → `test_attribution.py`, extend with cross-check)

**Frontend — modify:**
- `_components/chat/_citation_parse.ts` + `.test.ts` — chip grammar = `[N(:uuid)?, S. P]` / `[N, MM:SS]` only (drop `@offset`, `| keyword`, `#C`)
- `_components/chat/_citations.tsx` — drop offsets/spans/keyword from citation chips; keep popup exact-selection highlight
- `_components/chat/ChatMessage.tsx` — drop `buildDisplayContent`/`groundedLines` usage
- `_hooks/useChat.ts` — drop `line_done` handling + `groundedLines`
- `_components/viewer/PdfViewer.tsx`, `_components/viewer/_highlight.ts` (+ `.test.ts`) — remove citation-derived highlight; keep manual action-bar highlight
- `_types.ts` — drop `CitationHighlightSpan`, `groundedLines`, offset fields from citation types (keep popup_selection)

**Frontend — keep:** EmbedPDF action-bar manual highlight path (popup_selection / isExactSelection).

---

## Phase 1: Prompt — stop citation injection

### Task 1: Remove the CITATION FORMAT block from the RAG prompt

**Files:**
- Modify: `backend/src/tool_prompts.py` (`aia_system_rag`, the block from `"CITATION FORMAT (strict):\n"` through the few-shot examples)
- Test: `backend/tests/test_prompt_no_citation.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_prompt_no_citation.py
from src.tool_prompts import aia_system_rag

def test_prompt_has_no_citation_injection():
    p = aia_system_rag()
    assert "[N, #C" not in p          # no chunk-id chip instruction
    assert "CITATION FORMAT" not in p
    assert "keyword" not in p.lower() # no verbatim-keyword rule

def test_prompt_still_demands_grounded_answer():
    p = aia_system_rag()
    assert "ONLY" in p                # answer only from <documents>
    assert "NEVER invent" in p
```

- [ ] **Step 2: Run, expect FAIL**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_prompt_no_citation.py -q`
Expected: FAIL (`CITATION FORMAT` still present).

- [ ] **Step 3: Edit the prompt**

In `aia_system_rag`, delete the entire `"CITATION FORMAT (strict):\n"` section and all `"After EVERY sentence..."`, hard-rules, and few-shot example lines. Also remove the per-bullet/-row "carry its OWN citation" lines from RESPONSE STRUCTURE (lines about citations on every bullet/cell) and the docstring sentence about citation keywords. Keep: language rules, terminology rules, bullet/heading structure, no-invention, the no-info sentinel rule. The model now writes a clean grounded answer with NO chips.

- [ ] **Step 4: Run, expect PASS**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_prompt_no_citation.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tool_prompts.py backend/tests/test_prompt_no_citation.py
git commit -m "refactor(aia): drop citation injection from RAG prompt"
```

---

## Phase 2: Unified attribution + cross-check (new core logic, TDD)

### Task 2: Nav-only attribution chip (no offsets/keyword)

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py` (`_attribution_chip`)
- Test: `backend/tests/test_attribution.py` (rename from `test_generic_attribution.py`; keep `_pick_attribution` tests)

- [ ] **Step 1: Write the failing test**

```python
def _hit(sid, page, content, dist, start=None):
    return {"source_id": sid, "page_number": page, "content": content,
            "vec_distance": dist, "start_time": start}

def test_attribution_chip_is_nav_only_pdf():
    from src.features.ai_assistant.routes._helpers import _attribution_chip
    assert _attribution_chip(2, _hit(1, 12, "x", 0.2), "line") == ["[2, S. 12]"]

def test_attribution_chip_is_nav_only_media():
    from src.features.ai_assistant.routes._helpers import _attribution_chip
    chunk = {"source_id": 3, "page_number": None, "content": "x", "vec_distance": 0.2, "start_time": 92.0}
    assert _attribution_chip(3, chunk, "line") == ["[3, 01:32]"]
```

- [ ] **Step 2: Run, expect FAIL** (signature still takes `offset_fn`)

Run: `backend/.venv/bin/python -m pytest backend/tests/test_attribution.py -q`

- [ ] **Step 3: Rewrite `_attribution_chip`**

```python
def _attribution_chip(qnum: int, chunk: dict, line: str) -> list[str]:
    """Nav-only citation chip for a post-hoc attributed line: page (PDF) or the
    chunk's start timestamp (media). No span offset, no keyword — clicking only
    scrolls to the page/timestamp. `line` kept for signature stability/logging."""
    page = chunk.get("page_number")
    if page is None:
        st = chunk.get("start_time")
        return [f"[{qnum}, {_format_timestamp(st)}]"] if st is not None else []
    return [f"[{qnum}, S. {page}]"]
```

Remove `_overlap_phrase`/offset imports if now unused here.

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/features/ai_assistant/routes/_helpers.py backend/tests/test_attribution.py
git commit -m "refactor(aia): nav-only attribution chips (drop offset/keyword)"
```

### Task 3: Cross-check — only chip pages that were actually retrieved

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py` (`_attribute_generic_text` → add `seen_pages_by_source` param)
- Test: `backend/tests/test_attribution.py`

- [ ] **Step 1: Write the failing test**

```python
def _searcher(mapping):
    def search_one(line):
        for k, hits in mapping.items():
            if k in line:
                return hits
        return []
    return search_one

def test_crosscheck_accepts_retrieved_page():
    from src.features.ai_assistant.routes._helpers import _attribute_generic_text
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    out = _attribute_generic_text(
        line, _searcher({"substanzielle": [_hit(1, 12, "x", 0.2)]}),
        {1: 2}, seen_pages_by_source={1: {12}}, max_distance=0.6)
    assert out == f"{line} [2, S. 12]"

def test_crosscheck_drops_unretrieved_page():
    from src.features.ai_assistant.routes._helpers import _attribute_generic_text
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    out = _attribute_generic_text(
        line, _searcher({"substanzielle": [_hit(1, 99, "x", 0.2)]}),
        {1: 2}, seen_pages_by_source={1: {12}}, max_distance=0.6)
    assert out == line   # page 99 never retrieved -> no chip

def test_crosscheck_media_passes_when_source_retrieved():
    from src.features.ai_assistant.routes._helpers import _attribute_generic_text
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    hit = {"source_id": 3, "page_number": None, "content": "x", "vec_distance": 0.2, "start_time": 92.0}
    out = _attribute_generic_text(
        line, _searcher({"substanzielle": [hit]}),
        {3: 1}, seen_pages_by_source={3: set()}, max_distance=0.6)
    assert out == f"{line} [1, 01:32]"  # media: empty page-set means "source retrieved", accept
```

- [ ] **Step 2: Run, expect FAIL** (`seen_pages_by_source` param missing)

- [ ] **Step 3: Extend `_attribute_generic_text`**

New signature `(text, search_one, source_id_to_qnum, *, seen_pages_by_source=None, max_distance=_GENERIC_ATTRIB_MAX_DIST)`. After `_pick_attribution`, add the cross-check before building the chip:

```python
best = _pick_attribution(search_one(line) or [], max_distance)
if best is not None and seen_pages_by_source is not None:
    sid = best["source_id"]
    pages = seen_pages_by_source.get(sid)
    if pages is None:
        best = None                          # source never retrieved -> reject
    elif best.get("page_number") is not None and best["page_number"] not in pages:
        best = None                          # PDF page not in retrieved set -> reject
    # media (page_number None): empty/any set means source retrieved -> accept
qnum = source_id_to_qnum.get(best["source_id"]) if best else None
chips = _attribution_chip(qnum, best, line) if qnum else []
```

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/features/ai_assistant/routes/_helpers.py backend/tests/test_attribution.py
git commit -m "feat(aia): cross-check post-hoc attribution against retrieved pages"
```

---

## Phase 3: Wire chat.py to the unified path

### Task 4: Replace grounder + finalize with unified post-hoc for ALL RAG modes

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/chat.py` (`_stream`: ~1095–1440)

- [ ] **Step 1** — Delete the grounder construction block (the `_nav_only_all`, `coverage_sources`, `_unit_loader`, `_grounder = CitationGrounder(...)` setup ~1190–1199) and the per-line `feed_line`/`line_done` emission inside the stream loop. Keep the token yield and the line-buffer split that feeds the repetition guard ONLY (drop the grounding call + `line_done` yield).

- [ ] **Step 2** — Keep building `seen_pages_by_source` (already computed ~1174–1181) and hoist it above the stream so it is available in finalize.

- [ ] **Step 3** — Replace the whole finalize branch (`if post_hoc_generic: ... else: ...`, ~1287–1368) with ONE unified block for every RAG answer (not popup/direct):

```python
_clean_answer = _dedup_repeated_lines(_sanitize_citations("".join(answer_parts).strip()))
_stripped = _strip_inline_citation_chips(_clean_answer)  # defensive: model shouldn't emit chips now
from src.services.aia_embeddings import get_embedding_provider
_prov = get_embedding_provider()

def _attribute_blocking() -> str:
    _cands = [ln for ln in _stripped.split("\n") if _needs_attribution(ln)]
    _vec_by_line: dict[str, list] = {}
    if _cands:
        try:
            logger.info("post-hoc attribution: batch-embedding {} candidate lines in ONE call", len(_cands))
            _vecs = _prov.embed(_cands)
            if len(_vecs) == len(_cands):
                _vec_by_line = dict(zip(_cands, _vecs))
        except Exception as e:
            logger.warning("batch embedding failed, falling back per-line: {}", e)

    def _search_one(_line: str):
        try:
            _qv = _vec_by_line.get(_line) or _prov.embed_one(_line)
            return db.hybrid_search_chunks(workspace["id"], _line, _qv,
                                           source_ids=source_ids, limit=4)
        except Exception as e:
            logger.warning("attribution search failed for a line: {}", e)
            return []

    return _attribute_generic_text(_stripped, _search_one, source_id_to_qnum,
                                   seen_pages_by_source=seen_pages_by_source)

answer = await asyncio.to_thread(_attribute_blocking)
```

- [ ] **Step 4** — Remove `post_hoc_generic`, `scope_nav_only`, `scope_single_page`, `_scope_strip`, `do_fill`, `_offset_fn`, `_nav_only_chips`, `_append_scope_anchor`, `_strip_resolved_citation_chips` usages from `chat.py`. Scope answers now flow through the same unified attribution. The popup/`direct_text` path (`AIA_SYSTEM_DIRECT`) stays unchanged (no RAG attribution).

- [ ] **Step 5** — Remove the `chunk_registry`/`source_index`/`qnum_to_source_id` machinery only if unused after this; KEEP whatever `seen_pages_by_source` needs (it derives from `source_index`). Keep `source_qmap`, `source_id_to_qnum`, `all_sources_list`.

- [ ] **Step 6** — Run backend import + targeted run:

Run: `backend/.venv/bin/python -c "import src.features.ai_assistant.routes.chat" && backend/.venv/bin/python -m pytest backend/tests/test_attribution.py backend/tests/test_chat_paths.py -q`
Expected: import OK, tests PASS (fix any breakage from removed symbols).

- [ ] **Step 7: Commit**

```bash
git add backend/src/features/ai_assistant/routes/chat.py
git commit -m "refactor(aia): unify all RAG modes onto post-hoc attribution path"
```

### Task 5: Manual live verification (no test) — pages still correct

- [ ] Ask SPECIFIC ("Wann ist die Abgabe?"), GENERIC ("Überblick"), and scope ("fasse Seite 5 zusammen"). Confirm: chips appear (post-hoc, at end), each `[N, S. X]` jumps to the right page; no `@`/keyword in chips; no chip on unsupported lines. Check `docker logs kis-backend` for one `batch-embedding ... ONE call` per request and no traceback.

---

## Phase 4: Delete dead backend code + obsolete tests

### Task 6: Remove dead modules and helper functions

**Files:** delete `_grounding.py`, `_chunk_cite.py`, `_page_geometry.py`; trim `_helpers.py`; verify `_citation_match.py`.

- [ ] **Step 1** — Delete `_grounding.py`, `_chunk_cite.py`, `_page_geometry.py`. Remove their imports from `chat.py` and `_helpers.py`.
- [ ] **Step 2** — In `_helpers.py` delete: `resolve_citation_positions`, `fill_uncited_lines`, `_reground_by_line`, `_nav_only_chips`, `_strip_resolved_citation_chips`, `_append_scope_anchor`, `_highlights_enabled`, `_resolve_citation_pages` (if present), `SourceUnitLoader.offset_suffix`/`offset_suffixes`, `with_offsets` params anywhere, and any now-unused match/furniture helpers (`match_query` import, `_kw_is_furniture`, `_build_page_regions` if only used by removed code). Keep `_sanitize_citations`, `_strip_inline_citation_chips`, `_dedup_repeated_lines`, `_format_timestamp`, attribution helpers, `_needs_attribution`.
- [ ] **Step 3** — Grep for `_citation_match` usage. If only removed code referenced it, delete `_citation_match.py`; else keep (e.g. media `_format_timestamp`/`_parse_ts` may live elsewhere — move if needed).

Run: `cd backend && grep -rn "offset_suffix\|resolve_chunk_refs\|resolve_citation_positions\|fill_uncited_lines\|CitationGrounder\|_nav_only_chips\|_highlights_enabled\|with_offsets\|AIA_HIGHLIGHTS" src` → expect ZERO hits.

- [ ] **Step 4** — Delete obsolete test files (see File Structure list). Rename `test_generic_attribution.py` → `test_attribution.py` if not already.

- [ ] **Step 5** — Full backend suite:

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: all PASS (no import errors from deleted modules).

- [ ] **Step 6: Commit**

```bash
git add -A backend
git commit -m "chore(aia): delete live-grounding, chunk-id and offset machinery + obsolete tests"
```

---

## Phase 5: Frontend — simplify chips, remove citation highlights

### Task 7: Slim the citation grammar

**Files:** `_components/chat/_citation_parse.ts` (+ `.test.ts`)

- [ ] **Step 1** — Update `.test.ts`: chips are `[N, S. P]`, `[N:uuid, S. P]`, `[N, MM:SS]`, bare `[S. P]`. Remove tests asserting `@offset` parsing, `| keyword`, `#C`. Add a test that `[1, S. 12 @1-9 | x]` (legacy) still parses to page 12 with NO offsets/keyword (forward-tolerant) OR is treated as plain text — pick: forward-tolerant (ignore extras).
- [ ] **Step 2** — Run vitest, expect FAIL.
- [ ] **Step 3** — Simplify `citationPattern()` to `/[[【](?:Q?(\d+)(?::([a-f0-9]{6,64}))?,\s*)?(?:S\.\s*(\d+)|(\d{1,2}:\d{2}(?::\d{2})?))[^\]】]*[\]】]/g` (groups: 1=qnum 2=uuid 3=page 4=timestamp; trailing junk tolerated, discarded). Drop `offsets`/`keyword` from `CitationFields`. Simplify `sanitizeCitationsForMarkdown` (no `|`→`❘`, no URL-in-keyword scrub needed; keep the thematic-break + table-cell-tuck rules). Keep `stripCitations`.
- [ ] **Step 4** — Run vitest, expect PASS.
- [ ] **Step 5** — Commit.

### Task 8: Drop citation highlight from chips + viewer; keep popup highlight

**Files:** `_components/chat/_citations.tsx`, `_components/viewer/PdfViewer.tsx`, `_components/viewer/_highlight.ts` (+`.test.ts`), `_types.ts`

- [ ] **Step 1** — `_types.ts`: remove `CitationHighlightSpan`, `groundedLines`, and offset/keyword fields from citation-chip types. KEEP `popup_selection` + its exact-selection fields.
- [ ] **Step 2** — `_citations.tsx`: remove `clickOffsets`, `clickSpans`, `clickHighlight`(citation), span-grouping. Chip click passes only `(uuid, page, filename, sourceText?, startTime?, isExact?)`. The popup/exact branch (`isExactSelection`, `popup_selection`) STAYS and still passes its verbatim text for highlight. Adjacent same-page chips may still merge to one chip (visual only).
- [ ] **Step 3** — `PdfViewer.tsx` + `_highlight.ts`: delete the citation-derived highlight rendering (offsets/spans/keyword search). Keep the manual EmbedPDF action-bar highlight and the popup exact-selection highlight. Trim `_highlight.test.ts` to the kept behavior.
- [ ] **Step 4** — `useChat.ts` + `ChatMessage.tsx`: remove `line_done` event handling, `groundedLines`, and `buildDisplayContent`; render `sanitizeCitationsForMarkdown(msg.content)` directly.
- [ ] **Step 5** — Run vitest + typecheck:

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 6** — Commit.

### Task 9: Frontend live verification

- [ ] In the app: chips render `[N] S. X` / `[N] MM:SS`, click scrolls to page/timestamp, NO yellow citation highlight. Select text in the PDF → action-bar → highlight STILL works.

---

## Phase 6: Cleanup & docs

### Task 10: Remove flag + update memory/docs

- [ ] Remove `AIA_HIGHLIGHTS` from any `.env.example`, README, settings docs.
- [ ] Update memory notes that reference the now-removed machinery: `[[project-grounding-offset-only]]`, `[[project-docling-box-highlights]]`, `[[project-docling-overlay]]`, `[[project-llm-box-picker-highlights]]`, `[[project-strict-grounding-trace]]`, `[[project-citation-highlight-plain-anchor]]` — mark highlighting removed (except action-bar) and the single post-hoc attribution path as current.
- [ ] Commit.

---

## Self-Review Notes
- **Spec coverage:** injection removal (T1), unified path all modes (T4), cross-check (T3), highlight removal backend (T2,T6) + frontend (T8) + flag (T10), keep action-bar highlight (T8). ✓
- **Popup/direct path** deliberately untouched (not RAG citation). ✓
- **Risk:** scope summaries now attribute per line like generic — verify scope pages still land (T5). If scope regresses, add a scope-specific test before shipping.
- **Open verify:** whether `_citation_match.py` / `_build_page_regions` / furniture become fully unused (grep in T6 Step 3).
