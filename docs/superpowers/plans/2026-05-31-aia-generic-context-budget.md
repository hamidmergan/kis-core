# AIA Generic-Context Budget + Round-Robin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the GENERIC overview path's fixed per-source caps (30 page-summaries / 8 media chunks) and the hardcoded 200 000-char truncation with one tier-safe character budget that is filled round-robin across sources, so small models (32k) keep every source instead of silently dropping the late ones.

**Architecture:** Three moving parts in `backend/src/features/ai_assistant/routes/chat.py`: (1) tag each generic segment with a per-source sequence index `_seq` and raise the per-source ceiling to a high safety value; (2) a pure `_order_round_robin` helper that interleaves chunks by `(_seq, panel_order)` so truncation cuts late rounds fairly; (3) the shared context builder truncates at a named tier-safe constant instead of 200 000. The SPECIFIC path is untouched except that it inherits the smaller, tier-safe truncation constant (its chunks carry no `_seq`, so they keep today's grouped-by-source order).

**Tech Stack:** Python, FastAPI, pytest + pytest-asyncio. Tests are offline (DB monkeypatched). Run from `backend/`.

---

## File Structure

- **Modify:** `backend/src/limits.py` — add two named constants (`AIA_CONTEXT_MAX_CHARS`, `AIA_GENERIC_MAX_SEGMENTS_PER_SOURCE`).
- **Modify:** `backend/src/features/ai_assistant/routes/chat.py` — import the constants; add `_order_round_robin`; tag `_seq` + raise ceiling in `_assemble_generic_context` (multi-source branch only); replace the qnum sort and the `200000` literal in the shared context builder.
- **Modify:** `backend/tests/test_chat_paths.py` — update two now-stale generic tests; add round-robin + tagging tests.

No new files. Single-source generic and the SPECIFIC path keep their current behavior.

---

### Task 1: Tier-safe constants in limits.py

**Files:**
- Modify: `backend/src/limits.py` (after the `AIA_WORKSPACE_MAX_SOURCES` line, ~line 110)
- Modify: `backend/src/features/ai_assistant/routes/chat.py:23-28` (the `from src.limits import (...)` block)

- [ ] **Step 1: Add the constants**

In `backend/src/limits.py`, immediately after the line:

```python
AIA_WORKSPACE_MAX_SOURCES              = 30      # max sources per workspace
```

add:

```python

# --- AI tutor GENERIC context budget ----------------------------------------
# The overview path fills context round-robin across the active sources and
# truncates at this CHARACTER budget — sized for the smallest supported tier
# (Small, 8B / 32k context). Math: 32k tokens minus reserve for system prompt +
# question + history + answer ≈ ~24k tokens of context; at a conservative
# ~3.5 chars/token (mixed DE / non-Latin scripts) ≈ ~60k chars. Shared by the
# SPECIFIC path too (same context builder), so a topic answer also fits 32k.
# Raise this if a deployment only runs large models.
AIA_CONTEXT_MAX_CHARS                  = 60000
# Safety ceiling on how many summary/chunk segments ONE source contributes to a
# generic overview before round-robin + the char budget take over. Set well
# above AIA_SOURCE_MAX_PAGES (300) so PDFs are never down-sampled — every
# page-summary becomes a candidate and the budget, not this cap, decides what
# survives.
AIA_GENERIC_MAX_SEGMENTS_PER_SOURCE    = 900
```

- [ ] **Step 2: Import them in chat.py**

In `backend/src/features/ai_assistant/routes/chat.py`, change the limits import block from:

```python
from src.limits import (
    AIA_SOURCE_MAX_PAGES,
    AIA_WORKSPACE_MAX_SOURCES,
    AIA_WORKSPACE_MAX_ACCESS_LINKS,
    AIA_NOTES_MAX_PER_USER,
)
```

to:

```python
from src.limits import (
    AIA_SOURCE_MAX_PAGES,
    AIA_WORKSPACE_MAX_SOURCES,
    AIA_WORKSPACE_MAX_ACCESS_LINKS,
    AIA_NOTES_MAX_PER_USER,
    AIA_CONTEXT_MAX_CHARS,
    AIA_GENERIC_MAX_SEGMENTS_PER_SOURCE,
)
```

- [ ] **Step 3: Verify the import resolves**

Run: `cd backend && python -c "from src.features.ai_assistant.routes import chat; print(chat.AIA_CONTEXT_MAX_CHARS, chat.AIA_GENERIC_MAX_SEGMENTS_PER_SOURCE)"`
Expected: `60000 900`

- [ ] **Step 4: Commit**

```bash
git add backend/src/limits.py backend/src/features/ai_assistant/routes/chat.py
git commit -m "feat(rag): add tier-safe generic-context budget constants"
```

---

### Task 2: `_order_round_robin` pure helper

A stable reorder that interleaves chunks by their per-source sequence index `_seq` (missing → 0), with panel order (`source_id_to_qnum`) as the tie-breaker. Generic chunks carry `_seq` (Task 3) → they interleave; SPECIFIC chunks have no `_seq` → all sort as `_seq=0` → grouped by qnum exactly as today.

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/chat.py` (add the helper next to `_diversify_by_source`, after its definition ~line 323)
- Test: `backend/tests/test_chat_paths.py`

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_chat_paths.py`, add `_order_round_robin` to the imports from `chat`:

```python
from src.features.ai_assistant.routes.chat import (
    _should_skip_intent_classification,
    _sample,
    _assemble_generic_context,
    _diversify_by_source,
    _order_round_robin,
    _classify_intent,
    _rewrite_query,
    _split_doc_summary_by_markers,
    _INTENT_MAX_WORDS,
)
```

Then append this test section at the end of the file:

```python
# ── _order_round_robin: fair interleave for truncation ───────────────────────

def test_order_round_robin_interleaves_by_seq_then_source():
    chunks = [
        {"source_id": 1, "_seq": 0}, {"source_id": 1, "_seq": 1}, {"source_id": 1, "_seq": 2},
        {"source_id": 2, "_seq": 0}, {"source_id": 2, "_seq": 1}, {"source_id": 2, "_seq": 2},
    ]
    out = _order_round_robin(chunks, {1: 1, 2: 2})
    # round 0 of every source before any source's round 1
    assert [(c["source_id"], c["_seq"]) for c in out] == [
        (1, 0), (2, 0), (1, 1), (2, 1), (1, 2), (2, 2),
    ]


def test_order_round_robin_prefix_keeps_every_source():
    # A tiny source (1 segment) plus two big ones: any prefix of length
    # >= #sources contains all sources -> truncation never drops a whole source.
    chunks = (
        [{"source_id": 1, "_seq": i} for i in range(5)]
        + [{"source_id": 2, "_seq": i} for i in range(5)]
        + [{"source_id": 3, "_seq": 0}]
    )
    out = _order_round_robin(chunks, {1: 1, 2: 2, 3: 3})
    assert {c["source_id"] for c in out[:3]} == {1, 2, 3}


def test_order_round_robin_untagged_groups_by_qnum():
    # SPECIFIC chunks have no _seq -> all treated as seq 0 -> stable sort groups
    # by panel order, preserving within-source order (today's behavior).
    chunks = [
        {"source_id": 2, "page_number": 1},
        {"source_id": 1, "page_number": 9},
        {"source_id": 1, "page_number": 3},
    ]
    out = _order_round_robin(chunks, {1: 1, 2: 2})
    assert out == [
        {"source_id": 1, "page_number": 9},
        {"source_id": 1, "page_number": 3},
        {"source_id": 2, "page_number": 1},
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_chat_paths.py -k order_round_robin -v`
Expected: FAIL — `ImportError: cannot import name '_order_round_robin'`

- [ ] **Step 3: Implement the helper**

In `backend/src/features/ai_assistant/routes/chat.py`, after the `_diversify_by_source` function (it ends with `return diverse_chunks, remaining, missing`, ~line 323), add:

```python
def _order_round_robin(chunks: list[dict], source_id_to_qnum: dict[int, int]) -> list[dict]:
    """Interleave chunks so each source's Nth segment precedes any (N+1)th.

    Sorts stably by ``(_seq, panel_order)``: generic segments carry a per-source
    sequence index (``_seq`` 0,1,2…) so round 0 of every source comes first, then
    round 1, and so on — when the downstream char budget truncates, it cuts the
    late rounds and every source keeps its early (most representative) segments.

    Chunks without ``_seq`` (the SPECIFIC path) all sort as round 0, so the
    secondary panel-order key simply groups them by source as before.
    """
    return sorted(
        chunks,
        key=lambda c: (c.get("_seq", 0), source_id_to_qnum.get(c["source_id"], 0)),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_chat_paths.py -k order_round_robin -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/features/ai_assistant/routes/chat.py backend/tests/test_chat_paths.py
git commit -m "feat(rag): add _order_round_robin for fair multi-source truncation"
```

---

### Task 3: Tag `_seq` + raise ceiling in `_assemble_generic_context`

Multi-source generic now tags every segment with a per-source `_seq` and uses the high `AIA_GENERIC_MAX_SEGMENTS_PER_SOURCE` ceiling instead of 30/8. Single-source generic is left unchanged (one source → round-robin is a no-op; keeping it untagged preserves its existing exact-equality tests). Raw db dicts are copied (`{**c, "_seq": seq}`) so tagging never mutates DB-returned objects.

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/chat.py:257-302` (multi-source branch of `_assemble_generic_context`)
- Test: `backend/tests/test_chat_paths.py:195-222`

- [ ] **Step 1: Update the two now-stale tests + add a tagging test**

In `backend/tests/test_chat_paths.py`, replace `test_generic_multi_source_caps_page_summaries_per_source` (the body that asserts `{1: 30, 2: 30}`) with:

```python
def test_generic_multi_source_uses_all_summaries_and_tags_seq(monkeypatch):
    big = [{"page_number": i, "summary": f"S{i}"} for i in range(1, 60)]  # 59 each
    _patch_db(
        monkeypatch,
        sources=[{"id": 1, "summary": "d1"}, {"id": 2, "summary": "d2"}],
        page_sums={1: big, 2: big},
    )
    out = _assemble_generic_context(99, [1, 2])
    per_source = {}
    for c in out:
        per_source[c["source_id"]] = per_source.get(c["source_id"], 0) + 1
    # Ceiling is 900 >> 59 -> no down-sampling; every page-summary is a candidate.
    assert per_source == {1: 59, 2: 59}
    # Each source's segments are tagged with a contiguous per-source sequence.
    seqs_1 = [c["_seq"] for c in out if c["source_id"] == 1]
    assert seqs_1 == list(range(59))
```

And in `test_generic_multi_source_media_uses_raw_chunks`, change the two media assertions from capping at 8 to keeping all 20, and confirm tagging survives the dict copy:

```python
    out = _assemble_generic_context(99, [1, 2])
    media = [c for c in out if c["source_id"] == 2]
    # No 8-cap anymore: all raw media chunks are candidates (start_time preserved).
    assert len(media) == 20
    assert all(c.get("start_time") is not None for c in media)
    assert [c["_seq"] for c in media] == list(range(20))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_chat_paths.py -k "multi_source" -v`
Expected: FAIL — `assert {1: 59, 2: 59} == {1: 30, 2: 30}` style mismatch / `KeyError: '_seq'`

- [ ] **Step 3: Rewrite the multi-source branch**

In `backend/src/features/ai_assistant/routes/chat.py`, replace the entire multi-source `else:` block. The current block is:

```python
    else:
        # ── Multi-source overview ──
        # Each source contributes multiple anchored chunks so the LLM has equal
        # weight per source (otherwise media gets drowned out by PDFs):
        #   - PDFs: page-summaries (real page_number), capped to 30 evenly spaced.
        #   - Media: raw chunks (real start_time), capped to 8 evenly spaced.
        #   - Fallback: split doc-summary by inline markers, else first chunk.
        PAGE_SUMS_PER_SOURCE = 30
        MEDIA_CHUNKS_PER_SOURCE = 8
        for sid in source_ids:
            src = all_sources_map.get(sid)
            if not src:
                continue
            page_sums = db.get_page_summaries_by_source(sid)
            if page_sums:
                for ps in _sample(page_sums, PAGE_SUMS_PER_SOURCE):
                    chunks.append({
                        "source_id": sid,
                        "page_number": ps["page_number"],
                        "content": ps["summary"],
                        "start_time": None,
                    })
                continue
            # Media (no page-summaries by design): sample raw chunks. Their
            # start_time gives clickable timestamps; multiple chunks give the
            # LLM enough anchor points to actually cite the video.
            raw_chunks = db.get_aia_chunks_by_source(sid)
            if raw_chunks and any(c.get("start_time") is not None for c in raw_chunks):
                for c in _sample(raw_chunks, MEDIA_CHUNKS_PER_SOURCE):
                    chunks.append(c)
                continue
            doc_summary = (src.get("summary") or "").strip()
            if doc_summary:
                for seg in _split_doc_summary_by_markers(doc_summary):
                    chunks.append({
                        "source_id": sid,
                        "page_number": seg["page_number"],
                        "content": seg["content"],
                        "start_time": seg["start_time"],
                    })
                continue
            # Last resort: no page-summaries, no media chunks, no doc-summary.
            fallback = db.get_aia_chunks_by_source(sid)
            if fallback:
                chunks.extend(fallback)
        logger.info("Generic multi-source: {} segments across {} sources", len(chunks), len(source_ids))
```

Replace it with (note: `_seq` tagging per source, the new ceiling, and copied raw dicts):

```python
    else:
        # ── Multi-source overview ──
        # Each source contributes anchored segments, tagged with a per-source
        # sequence index (_seq). Downstream they are ordered round-robin and
        # truncated at the char budget, so every source keeps its early segments
        # instead of late sources being dropped wholesale (see _order_round_robin):
        #   - PDFs: page-summaries (real page_number).
        #   - Media: raw chunks (real start_time).
        #   - Fallback: split doc-summary by inline markers, else raw chunks.
        # The per-source ceiling is a high safety bound; the budget, not the cap,
        # decides what survives.
        cap = AIA_GENERIC_MAX_SEGMENTS_PER_SOURCE
        for sid in source_ids:
            src = all_sources_map.get(sid)
            if not src:
                continue
            seq = 0
            page_sums = db.get_page_summaries_by_source(sid)
            if page_sums:
                for ps in _sample(page_sums, cap):
                    chunks.append({
                        "source_id": sid,
                        "page_number": ps["page_number"],
                        "content": ps["summary"],
                        "start_time": None,
                        "_seq": seq,
                    })
                    seq += 1
                continue
            # Media (no page-summaries by design): raw chunks. Their start_time
            # gives clickable timestamps; multiple chunks give the LLM enough
            # anchor points to actually cite the video.
            raw_chunks = db.get_aia_chunks_by_source(sid)
            if raw_chunks and any(c.get("start_time") is not None for c in raw_chunks):
                for c in _sample(raw_chunks, cap):
                    chunks.append({**c, "_seq": seq})
                    seq += 1
                continue
            doc_summary = (src.get("summary") or "").strip()
            if doc_summary:
                for segment in _split_doc_summary_by_markers(doc_summary):
                    chunks.append({
                        "source_id": sid,
                        "page_number": segment["page_number"],
                        "content": segment["content"],
                        "start_time": segment["start_time"],
                        "_seq": seq,
                    })
                    seq += 1
                continue
            # Last resort: no page-summaries, no media chunks, no doc-summary.
            fallback = db.get_aia_chunks_by_source(sid)
            for c in fallback:
                chunks.append({**c, "_seq": seq})
                seq += 1
        logger.info("Generic multi-source: {} segments across {} sources", len(chunks), len(source_ids))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_chat_paths.py -k "generic" -v`
Expected: PASS — including the unchanged single-source tests (still no `_seq`) and the updated multi-source tests.

- [ ] **Step 5: Commit**

```bash
git add backend/src/features/ai_assistant/routes/chat.py backend/tests/test_chat_paths.py
git commit -m "feat(rag): tag generic segments per-source, drop fixed 30/8 caps"
```

---

### Task 4: Wire round-robin + the budget constant into the handler

Replace the grouped-by-qnum sort with `_order_round_robin`, and the `200000` truncation literal with `AIA_CONTEXT_MAX_CHARS`. This is an integration change inside the streaming chat handler; coverage comes from Tasks 2–3 plus the full suite staying green.

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/chat.py:540-543` (the sort) and `:556`, `:576` (the truncation comment + literal)

- [ ] **Step 1: Replace the sort with round-robin ordering**

Change:

```python
    # Render context blocks in Q-number order so <document index="N"> runs 1,2,3…
    # and the 200k truncation favors the lower-numbered sources. Stable sort keeps
    # each source's chunks in their original page/timestamp order.
    chunks.sort(key=lambda c: source_id_to_qnum.get(c["source_id"], 0))
```

to:

```python
    # Order round-robin: each source's Nth segment before any (N+1)th, so the
    # char-budget truncation below cuts late rounds and every source keeps its
    # early segments. SPECIFIC chunks carry no _seq -> grouped by panel order as
    # before. See _order_round_robin.
    chunks = _order_round_robin(chunks, source_id_to_qnum)
```

- [ ] **Step 2: Replace the truncation literal**

Change the comment:

```python
    # Build context (max 200000 chars) - XML tags per chunk (Anthropic best practice).
```

to:

```python
    # Build context (capped at AIA_CONTEXT_MAX_CHARS) - XML tags per chunk (Anthropic best practice).
```

and change:

```python
        if context_len + len(part) > 200000:
            break
```

to:

```python
        if context_len + len(part) > AIA_CONTEXT_MAX_CHARS:
            break
```

- [ ] **Step 3: Confirm no other `200000` literal remains in this file**

Run: `cd backend && grep -n "200000" src/features/ai_assistant/routes/chat.py`
Expected: no output (empty).

- [ ] **Step 4: Run the full chat-paths suite**

Run: `cd backend && python -m pytest tests/test_chat_paths.py -v`
Expected: PASS — all tests (routing, rewrite, sample, generic assembly + tagging, diversify, round-robin) green.

- [ ] **Step 5: Run the broader backend suite to catch regressions**

Run: `cd backend && python -m pytest -q`
Expected: PASS — no regressions from the sort/truncation change (the sister-spec's ~168 chat tests included).

- [ ] **Step 6: Commit**

```bash
git add backend/src/features/ai_assistant/routes/chat.py
git commit -m "feat(rag): fill generic context round-robin within tier-safe budget"
```

---

## Out of scope (do not implement here)

- Tier UI / preset dropdown, per-model `context_window` field, admin "context budget" setting — escape hatch is editing the `limits.py` constant.
- Doc-summary swap for very large docs (use the coherent doc-summary instead of N scattered page-summaries when a source's allotted segments cover little of it).
- SPECIFIC-path reordering. It inherits only the tier-safe truncation constant.

## Post-implementation follow-ups (not tasks)

- Confirm `AIA_CONTEXT_MAX_CHARS` (60000) empirically across the three model tiers + a non-German source ([[project-tier-testing-pending]]).
- Verify the citation resolver tolerates interleaved `<document index="N">` runs (indices now repeat: 1,2,3,1,2,3). `source_index` is aggregated by `qn`, so this is expected to be fine — confirm with a live generic multi-source query (Playwright smoke in the sister spec).
