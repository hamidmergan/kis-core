# Real-time Citation Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ground each answer line the moment its newline arrives so chips appear already correct (right page + `@offsets`) and never change on click — the raw LLM chip is never shown.

**Architecture:** A new stateful `CitationGrounder` reuses the existing per-line grounding functions. `chat.py`'s `_stream()` buffers tokens into lines, grounds each completed line in a worker thread, and emits a new `line_done` SSE event. The frontend keeps a `groundedLines` overlay and renders grounded lines (with chips) while stripping raw chips from not-yet-grounded text. The final `done` event still carries the canonical full-pipeline answer, which reconciles the two rare edge cases (summary section, table header at stream tip).

**Tech Stack:** Python (FastAPI SSE, pytest in `kis-backend` container), TypeScript/React (Next.js, Vitest).

**Spec:** `docs/superpowers/specs/2026-06-03-aia-realtime-citation-grounding-design.md`

**Test commands:**
- Backend: `make test-backend ARGS="tests/<file> -v"` (needs the dev stack up: `docker compose -f docker-compose.dev.yml up -d`)
- Frontend: `cd frontend && npx vitest run <path>`

---

## File Structure

- **Modify** `backend/src/features/ai_assistant/routes/_helpers.py` — move `_sanitize_citations` + its two regexes here (they are citation helpers; `_grounding.py` needs them without importing `chat.py`).
- **Create** `backend/src/features/ai_assistant/routes/_grounding.py` — `CitationGrounder` (per-line incremental grounding).
- **Modify** `backend/src/features/ai_assistant/routes/chat.py` — import `_sanitize_citations` from `_helpers`; build loader/coverage before the token loop; emit `line_done`.
- **Create** `backend/tests/test_citation_incremental.py` — grounder parity + incremental tests.
- **Modify** `frontend/src/app/[locale]/workspace/[uuid]/_types.ts` — add `groundedLines?` to `ChatMessage`.
- **Modify** `frontend/src/app/[locale]/workspace/[uuid]/_components/chat/_citation_parse.ts` — add pure `buildDisplayContent`.
- **Modify** `frontend/src/app/[locale]/workspace/[uuid]/_components/chat/_citation_parse.test.ts` — test `buildDisplayContent`.
- **Modify** `frontend/src/app/[locale]/workspace/[uuid]/_hooks/useChat.ts` — handle `line_done`; clear overlay on `done`.
- **Modify** `frontend/src/app/[locale]/workspace/[uuid]/_components/chat/ChatMessage.tsx` — render via `buildDisplayContent`.

---

## Task 1: Move `_sanitize_citations` into `_helpers.py`

Pure refactor so `_grounding.py` can reuse it without importing `chat.py`. No behaviour change.

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py`
- Modify: `backend/src/features/ai_assistant/routes/chat.py:59-67` (remove local copy), `chat.py:352-375` (add to the existing `_helpers` import block)
- Test: `backend/tests/test_citation_incremental.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_citation_incremental.py`:

```python
from src.features.ai_assistant.routes._helpers import _sanitize_citations


def test_sanitize_repairs_page_and_time():
    assert _sanitize_citations("Foo [1] S. 3 bar") == "Foo [1, S. 3] bar"
    assert _sanitize_citations("Clip [2] 05:32 end") == "Clip [2, 05:32] end"
```

- [ ] **Step 2: Run it — expect ImportError**

Run: `make test-backend ARGS="tests/test_citation_incremental.py -v"`
Expected: FAIL — `ImportError: cannot import name '_sanitize_citations' from ...._helpers`

- [ ] **Step 3: Add the function + regexes to `_helpers.py`**

Near the top of `_helpers.py` (after the existing `import re`), add:

```python
# Smaller models sometimes emit `[N] S. X` or `[N] MM:SS` (closing the bracket
# before the position label). Repair to `[N, S. X]` / `[N, MM:SS]` so the chip
# parser renders them as clickable citations.
_CITATION_FIX_TIME_RE = re.compile(r"\[(\d+)\]\s+(\d{1,2}:\d{2}(?::\d{2})?)")
_CITATION_FIX_PAGE_RE = re.compile(r"\[(\d+)\]\s+(S\.\s*\d+(?:[-,–]\s*\d+)*)")


def _sanitize_citations(text: str) -> str:
    """Repair malformed `[N] pos` citations into the chip-renderable `[N, pos]` form."""
    text = _CITATION_FIX_TIME_RE.sub(r"[\1, \2]", text)
    text = _CITATION_FIX_PAGE_RE.sub(r"[\1, \2]", text)
    return text
```

- [ ] **Step 4: Import it in `chat.py`, delete the local copy**

In `chat.py`, delete the local `_CITATION_FIX_TIME_RE`, `_CITATION_FIX_PAGE_RE`, and `_sanitize_citations` (the block at lines 59-67). Add `_sanitize_citations` to the existing import from `._helpers` (the block starting `from src.features.ai_assistant.routes._helpers import (`):

```python
from src.features.ai_assistant.routes._helpers import (
    _trace_llm,
    _sanitize_citations,
    # ... keep all existing names ...
)
```

- [ ] **Step 5: Run the test + the full citation suite — expect PASS**

Run: `make test-backend ARGS="tests/test_citation_incremental.py tests/test_citation_resolve.py tests/test_citation_offsets.py -v"`
Expected: PASS (no regression — the function is unchanged, only relocated).

- [ ] **Step 6: Commit**

```bash
git add backend/src/features/ai_assistant/routes/_helpers.py backend/src/features/ai_assistant/routes/chat.py backend/tests/test_citation_incremental.py
git commit -m "refactor(aia): move _sanitize_citations to _helpers"
```

---

## Task 2: `CitationGrounder` (per-line incremental grounding)

**Files:**
- Create: `backend/src/features/ai_assistant/routes/_grounding.py`
- Test: `backend/tests/test_citation_incremental.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_citation_incremental.py`:

```python
from src.features.ai_assistant.routes._grounding import CitationGrounder
from src.features.ai_assistant.routes._citation_match import Unit


class _Loader:
    """Minimal SourceUnitLoader stand-in: only .units (no offsets/furniture),
    so chips ground to a page+keyword without @offset suffixes."""
    def __init__(self, by_id):
        self._by_id = by_id

    def units(self, source, *, is_media):
        return self._by_id[source["id"]]


def _sources(units_by_id):
    # qnum -> {source, is_media, pages}
    return {
        qn: {"source": {"id": qn}, "is_media": False,
             "pages": {u.page for u in units if u.page is not None}}
        for qn, units in units_by_id.items()
    }


def test_feed_line_grounds_existing_citation():
    units = {1: [Unit(3, None, None, "Dezimalbrueche sind Brueche mit Nenner 10")]}
    g = CitationGrounder(_sources(units), _Loader(units), [{"qnum": 1, "uuid": "u1", "filename": "f.pdf"}])
    out = g.feed_line("Es geht um Dezimalbrueche. [1, S. 9 | Dezimalbrueche]")
    # page corrected from the bogus 9 to the unit's real page 3
    assert "[1, S. 3" in out
    assert "S. 9" not in out


def test_feed_line_keeps_summary_chip_free_after_cited_body():
    units = {1: [Unit(2, None, None, "Die Methode nutzt einen Test")]}
    g = CitationGrounder(_sources(units), _Loader(units),
                         [{"qnum": 1, "uuid": "u1", "filename": "f.pdf"}])
    g.feed_line("Die Methode nutzt einen Test. [1, S. 2 | Test]")  # cited body
    g.feed_line("Zusammenfassung")                                  # heading
    out = g.feed_line("Die Methode nutzt einen Test. [1, S. 2 | Test]")  # recap
    assert "[1" not in out  # stripped inside summary


def test_feed_sequence_matches_full_pipeline_for_prose():
    # The line-by-line result joined equals the canonical batch grounding for a
    # plain prose answer (the common, must-be-flicker-free case).
    from src.features.ai_assistant.routes._helpers import (
        resolve_citation_positions, fill_uncited_lines, _sanitize_citations, _chipify_inline_refs,
    )
    units = {1: [Unit(4, None, None, "Der Algorithmus sortiert in n log n Schritten")]}
    src, loader = _sources(units), _Loader(units)
    qmap = [{"qnum": 1, "uuid": "u1", "filename": "f.pdf"}]
    answer = "Der Algorithmus sortiert schnell. [1, S. 1 | Algorithmus]\nDas ist wichtig."

    # canonical batch pipeline
    canon = _chipify_inline_refs(_sanitize_citations(answer), qmap)
    canon = resolve_citation_positions(canon, src, loader)
    canon = fill_uncited_lines(canon, src, loader)

    # incremental
    g = CitationGrounder(src, loader, qmap)
    inc = "\n".join(g.feed_line(line) for line in answer.split("\n"))
    assert inc == canon
```

- [ ] **Step 2: Run — expect ImportError**

Run: `make test-backend ARGS="tests/test_citation_incremental.py -v"`
Expected: FAIL — `ModuleNotFoundError: ..._grounding`

- [ ] **Step 3: Implement `_grounding.py`**

Create `backend/src/features/ai_assistant/routes/_grounding.py`:

```python
"""Per-line incremental citation grounding for the streaming chat answer.

Reuses the exact per-line functions the post-stream batch path uses
(`resolve_citation_positions`, `fill_uncited_lines`), plus the summary-strip rule,
so a line grounded live equals what the canonical pipeline produces — except the two
edge cases documented in the spec (multi summary headings, table header at the
streaming tip), which the final `done` event reconciles.
"""
from __future__ import annotations

import re

from ._helpers import (
    _CITE_RESOLVE_RE,
    _SUMMARY_HEADING_RE,
    _chipify_inline_refs,
    _sanitize_citations,
    fill_uncited_lines,
    resolve_citation_positions,
)


class CitationGrounder:
    """Grounds one answer line at a time, carrying summary state across lines.

    sources: {qnum: {"source": row, "is_media": bool, "pages": set}} (coverage shape)
    loader:  SourceUnitLoader (or a stub exposing .units / optional .offset_suffixes /
             .furniture).
    source_qmap: the [{qnum, uuid, filename, is_media}] list (for _chipify_inline_refs).
    """

    def __init__(self, sources: dict, loader, source_qmap: list) -> None:
        self._sources = sources
        self._loader = loader
        self._qmap = source_qmap
        self._in_summary = False
        self._seen_cited_body = False

    def feed_line(self, line: str) -> str:
        line = _sanitize_citations(line)
        line = _chipify_inline_refs(line, self._qmap)
        if _SUMMARY_HEADING_RE.match(line):
            self._in_summary = True
        resolved = resolve_citation_positions(line, self._sources, self._loader)
        if self._in_summary:
            # Mirror _strip_summary_citations: only strip once a cited body has
            # preceded the heading; otherwise this is a summary-style TITLE and we
            # leave the (resolved) chips. Summary lines never get fill (matches the
            # in_summary gate inside fill_uncited_lines).
            if self._seen_cited_body:
                resolved = _CITE_RESOLVE_RE.sub("", resolved)
                resolved = re.sub(r"[ \t]+([.,;:!?])", r"\1", resolved)
                resolved = re.sub(r"[ \t]{2,}", " ", resolved).rstrip()
            return resolved
        resolved = fill_uncited_lines(resolved, self._sources, self._loader)
        if _CITE_RESOLVE_RE.search(resolved):
            self._seen_cited_body = True
        return resolved
```

- [ ] **Step 4: Run — expect PASS**

Run: `make test-backend ARGS="tests/test_citation_incremental.py -v"`
Expected: PASS (3 new tests + the sanitize test).

- [ ] **Step 5: Commit**

```bash
git add backend/src/features/ai_assistant/routes/_grounding.py backend/tests/test_citation_incremental.py
git commit -m "feat(aia): CitationGrounder for per-line incremental grounding"
```

---

## Task 3: Emit `line_done` from the chat stream

Wire the grounder into `_stream()`. Integration glue (no unit test — verified by the running app and Task 2's unit coverage); the canonical `done` answer is unchanged.

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/chat.py` (inside `_stream`, around lines 790-862 and 868-878)

- [ ] **Step 1: Import the grounder**

Add near the other route imports in `chat.py`:

```python
from src.features.ai_assistant.routes._grounding import CitationGrounder
```

- [ ] **Step 2: Build loader + coverage ONCE, before the token loop**

The canonical block currently builds `_unit_loader` and `coverage_sources` *after* the LLM loop (around lines 868-878). Move that construction to the top of `_stream()`, right after the `yield ... qmap ...` line, so it is available during streaming. Replace the later in-place construction with a reference to these.

In `_stream`, immediately after:

```python
            yield f"data: {json.dumps({'qmap': source_qmap, 'source_pages': source_pages})}\n\n"
```

insert:

```python
            # Built once here (was previously built after the loop) so each line can
            # be grounded live. Reused by the canonical finalize block below.
            coverage_sources = {
                qn: {"source": all_sources_list[qnum_to_source_id[qn]],
                     "is_media": source_index[qn]["is_media"],
                     "pages": source_index[qn].get("pages", set())}
                for qn in source_index if qnum_to_source_id.get(qn) in all_sources_list
            }
            _unit_loader = SourceUnitLoader()
            _grounder = CitationGrounder(coverage_sources, _unit_loader, source_qmap)
            _line_buf = ""
            _line_idx = 0
```

Then in the canonical block after the loop, DELETE the now-duplicate construction of `coverage_sources` and `_unit_loader` (lines ~868-878), keeping the rest (`_chipified = ...`, `resolve_citation_positions(...)`, `fill_uncited_lines(...)`) which now uses the variables built above.

- [ ] **Step 3: Buffer tokens into lines and emit `line_done`**

In the token loop, the existing branch is:

```python
                    if delta and delta.content:
                        answer_parts.append(delta.content)
                        yield f"data: {json.dumps({'token': delta.content})}\n\n"
```

Replace it with:

```python
                    if delta and delta.content:
                        answer_parts.append(delta.content)
                        yield f"data: {json.dumps({'token': delta.content})}\n\n"
                        _line_buf += delta.content
                        while "\n" in _line_buf:
                            _completed, _line_buf = _line_buf.split("\n", 1)
                            _grounded = await asyncio.to_thread(_grounder.feed_line, _completed)
                            yield f"data: {json.dumps({'line_done': {'index': _line_idx, 'text': _grounded}})}\n\n"
                            _line_idx += 1
```

- [ ] **Step 4: Flush the final partial line after the loop**

Directly after the `while True:` streaming loop ends (before the `except Exception` / after the normal break — i.e. right before the existing `# First repair malformed ...` comment), add:

```python
            # Flush the last line (no trailing newline) so its chip grounds too.
            if _line_buf.strip():
                _grounded = await asyncio.to_thread(_grounder.feed_line, _line_buf)
                yield f"data: {json.dumps({'line_done': {'index': _line_idx, 'text': _grounded}})}\n\n"
                _line_idx += 1
            _line_buf = ""
```

- [ ] **Step 5: Restart backend, verify the event appears**

```bash
docker compose -f docker-compose.dev.yml restart kis-backend
```

Verification: send a chat question in the app (frontend :3000) against a workspace with a PDF source. Tail the backend log and confirm `line_done` frames are emitted during streaming:

```bash
docker compose -f docker-compose.dev.yml logs -f kis-backend | grep -i "Context sent\|stream"
```

Expected: the answer still streams and saves normally; no errors. (Frontend will ignore the unknown `line_done` event until Task 6 — that is fine.)

- [ ] **Step 6: Commit**

```bash
git add backend/src/features/ai_assistant/routes/chat.py
git commit -m "feat(aia): emit per-line line_done grounding events during chat stream"
```

---

## Task 4: Frontend type — `groundedLines`

**Files:**
- Modify: `frontend/src/app/[locale]/workspace/[uuid]/_types.ts:64-72`

- [ ] **Step 1: Add the field**

In the `ChatMessage` interface, after `aborted?: boolean;`, add:

```typescript
  // Overlay filled by `line_done` stream events: index i holds the grounded text of
  // answer line i. Undefined entries fall back to the raw (chip-stripped) line.
  groundedLines?: (string | undefined)[];
```

- [ ] **Step 2: Verify it type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/[locale]/workspace/[uuid]/_types.ts
git commit -m "feat(aia): add groundedLines to ChatMessage type"
```

---

## Task 5: `buildDisplayContent` pure helper

**Files:**
- Modify: `frontend/src/app/[locale]/workspace/[uuid]/_components/chat/_citation_parse.ts`
- Test: `frontend/src/app/[locale]/workspace/[uuid]/_components/chat/_citation_parse.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `_citation_parse.test.ts`:

```typescript
import { buildDisplayContent } from "./_citation_parse";

describe("buildDisplayContent", () => {
  it("returns content unchanged when not streaming", () => {
    const c = "A [1, S. 2 | k]\nB";
    expect(buildDisplayContent(c, undefined, false)).toBe(c);
  });

  it("strips raw chips from ungrounded lines while streaming", () => {
    const c = "A [1, S. 2 | k]\nB [1, S. 3 | k]";
    expect(buildDisplayContent(c, undefined, true)).toBe("A \nB ");
  });

  it("uses the grounded text for grounded lines, strips the rest", () => {
    const c = "A [1, S. 9 | k]\nB [1, S. 9 | k]";
    const grounded = ["A [1, S. 2 @10-20 | k]"]; // only line 0 grounded
    expect(buildDisplayContent(c, grounded, true)).toBe("A [1, S. 2 @10-20 | k]\nB ");
  });
});
```

- [ ] **Step 2: Run — expect failure**

Run: `cd frontend && npx vitest run src/app/\[locale\]/workspace/\[uuid\]/_components/chat/_citation_parse.test.ts`
Expected: FAIL — `buildDisplayContent is not a function`.

- [ ] **Step 3: Implement it**

Append to `_citation_parse.ts`:

```typescript
// Compose the text shown for an assistant message. While streaming, grounded lines
// (filled by `line_done`) are shown verbatim (their chips are already correct); every
// other line has its raw LLM chips stripped, so an unverified chip is never visible.
// Once streaming is done the canonical `content` is rendered unchanged.
export function buildDisplayContent(
  content: string,
  groundedLines: (string | undefined)[] | undefined,
  streaming: boolean,
): string {
  if (!streaming) return content;
  const g = groundedLines ?? [];
  return content
    .split("\n")
    .map((raw, i) => g[i] ?? stripCitations(raw))
    .join("\n");
}
```

- [ ] **Step 4: Run — expect PASS**

Run: `cd frontend && npx vitest run src/app/\[locale\]/workspace/\[uuid\]/_components/chat/_citation_parse.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/[locale]/workspace/[uuid]/_components/chat/_citation_parse.ts frontend/src/app/[locale]/workspace/[uuid]/_components/chat/_citation_parse.test.ts
git commit -m "feat(aia): buildDisplayContent overlay helper for streaming chips"
```

---

## Task 6: Handle `line_done` in `useChat`

**Files:**
- Modify: `frontend/src/app/[locale]/workspace/[uuid]/_hooks/useChat.ts:173-196`

- [ ] **Step 1: Add the `line_done` branch**

In `processLine`, after the `evt.qmap` branch and before `evt.done`, add:

```javascript
            } else if (evt.line_done) {
              const { index, text } = evt.line_done as { index: number; text: string };
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last) {
                  const gl = last.groundedLines ? [...last.groundedLines] : [];
                  gl[index] = text;
                  updated[updated.length - 1] = { ...last, groundedLines: gl };
                }
                return updated;
              });
```

- [ ] **Step 2: Clear the overlay on `done`**

In the `evt.done` branch, the patch object is built as:

```javascript
              const patch: Record<string, unknown> = { source_pages: evt.source_pages, source_qmap: evt.source_qmap };
              if (evt.answer) patch.content = evt.answer;
```

Add a line so the canonical answer renders without the overlay:

```javascript
              patch.groundedLines = undefined;
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/[locale]/workspace/[uuid]/_hooks/useChat.ts
git commit -m "feat(aia): track groundedLines overlay from line_done events"
```

---

## Task 7: Render via `buildDisplayContent` in `ChatMessage`

**Files:**
- Modify: `frontend/src/app/[locale]/workspace/[uuid]/_components/chat/ChatMessage.tsx` (import line ~11 region, render at line 248)

- [ ] **Step 1: Import the helper**

Find the import of `sanitizeCitationsForMarkdown` (from `./_citation_parse`) and add `buildDisplayContent` to it, e.g.:

```typescript
import { sanitizeCitationsForMarkdown, buildDisplayContent } from "./_citation_parse";
```

(If `sanitizeCitationsForMarkdown` is imported on a different line, add `buildDisplayContent` to that same `./_citation_parse` import.)

- [ ] **Step 2: Use the overlay for the markdown source**

At line 248, replace:

```jsx
                  {sanitizeCitationsForMarkdown(msg.content)}
```

with:

```jsx
                  {sanitizeCitationsForMarkdown(buildDisplayContent(msg.content, msg.groundedLines, isStreaming))}
```

(`isStreaming` already exists in this component: `const isStreaming = loading && isLatest;`.)

- [ ] **Step 3: Type-check + run the frontend unit suite**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: no errors; all tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/[locale]/workspace/[uuid]/_components/chat/ChatMessage.tsx
git commit -m "feat(aia): render streaming answer through grounded-lines overlay"
```

---

## Task 8: End-to-end manual verification

**Files:** none (verification only).

- [ ] **Step 1: Bring up the stack**

```bash
docker compose -f docker-compose.dev.yml up -d
```

- [ ] **Step 2: Verify the behaviour**

In the app (frontend :3000, login `a`/`a`), open a workspace with at least one PDF source and ask a content question.

Confirm, in order:
1. While Hilde streams, prose appears **without** any `[…]` chips in the not-yet-finished tail.
2. Grounded chips pop in ~one line behind the text, already showing the correct page.
3. Clicking a chip during streaming highlights the correct span.
4. After "done", clicking the **same** chip highlights the **same** span (no change, none removed) — except possibly inside a "Zusammenfassung/Summary" section (accepted reconciliation).

- [ ] **Step 3: Confirm backend unit suite is green**

Run: `make test-backend ARGS="tests/test_citation_incremental.py tests/test_citation_resolve.py tests/test_citation_offsets.py tests/test_source_streaming.py -v"`
Expected: PASS.

---

## Self-Review Notes

- **Spec coverage:** §1 protocol → Task 3; §2 grounder → Tasks 1-2; §3 frontend overlay → Tasks 4-7; §4 reconciliation → Task 2 summary test + Task 6 `done` clear; §5 edge cases → Task 3 flush / Task 8; §6 testing → Tasks 2, 5, 8.
- **No placeholders:** every code step is concrete.
- **Type consistency:** `groundedLines: (string|undefined)[]` is used identically in `_types.ts`, `useChat.ts`, `buildDisplayContent`, and `ChatMessage.tsx`; the `line_done` payload `{index, text}` matches between `chat.py` emit and `useChat.ts` read; `CitationGrounder(sources, loader, source_qmap)` signature matches between Task 2 def and Task 3 use.
