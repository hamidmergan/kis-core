# Real-time citation grounding (AIA highlight UX)

**Date:** 2026-06-03
**Branch:** `feat/optimize-aia-highlight-ux`
**Status:** Experiment — keep if it works, otherwise discard.

## Problem

During chat streaming, inline citation chips (`[Q1, S. 3 | keyword]`) are emitted
raw by the LLM and rendered live. They are **unverified**: page may be wrong, no
`@start-end` offsets yet. A user can click such a chip and get highlight A. After the
stream finishes, the same chip is re-grounded (page corrected, offsets added) or even
removed — a second click then yields highlight B, or the chip is gone. This
inconsistency feels broken.

Root cause: the live chip is the LLM's raw claim; grounding only runs once, after the
full stream, in a single post-pass (`resolve_citation_positions` →
`fill_uncited_lines` → `_strip_summary_citations`, see `routes/chat.py` `_stream`).

## Goal

The user must **never see a raw LLM chip**. Chips appear already grounded
(correct page + offsets, or not at all), as fast as possible — even while the answer
is still streaming. A chip, once shown, should not change on click.

## Key enabler

Grounding needs only the **completed line**, not the whole answer, and is pure Python
(string match + pdfium page-text lookup) — no LLM. `resolve_citation_positions` and
`fill_uncited_lines` already iterate line-by-line. So a line can be grounded the
moment its newline arrives.

## Approach A — per-line incremental grounding

Prose keeps streaming live as raw tokens (for the typing feel). When a line completes,
the backend grounds it and pushes the finished chip. The frontend suppresses raw chips
in not-yet-grounded text, so only grounded chips are ever visible. Chips lag the text
by ~1 line.

### 1. Backend — stream protocol

`routes/chat.py` `_stream()` SSE events:

- `{qmap, source_pages}` — unchanged (first event).
- `{token: "..."}` — unchanged (raw prose delta, drives the live text flow).
- **NEW** `{line_done: {index, text}}` — emitted whenever a `\n` completes a line.
  `index` is the 0-based line number in the answer; `text` is the fully grounded line
  (with `@start-end | kw` chips, or chip removed/added per the grounding rules).
- `{done, answer, source_pages, source_qmap}` — unchanged in shape; `answer` is the
  **canonical** full grounding (authoritative reconciliation, see §4).

### 2. Backend — incremental grounder

New stateful helper in `routes/_helpers.py` (or a sibling module), reusing the existing
per-line logic so behaviour stays identical:

```
class CitationGrounder:
    def __init__(self, coverage_sources, unit_loader, source_qmap): ...
    def feed_line(self, line: str) -> str        # ground ONE line; keeps in_summary state
    def finalize(self, full_text: str) -> str     # canonical full pipeline (== today)
```

- `feed_line` runs the same per-line steps the batch path runs: sanitize →
  chipify (already global/whitespace-safe) → `resolve_citation_positions` core for that
  line → `fill_uncited_lines` core for that line. It carries the `in_summary` flag and
  the one-line table-header lookahead internally.
- `finalize` runs the existing full pipeline unchanged and returns the authoritative
  answer (what `{done}` carries and what is persisted).
- Per-line grounding in `_stream` runs via `asyncio.to_thread(...)` so it never blocks
  the event loop / token forwarding. pdfium page text is cached per page
  (`SourceUnitLoader` / `_page_text_cache`), so repeated cites to a page are cheap.

### 3. Frontend — overlay rendering (no raw chip ever)

`_hooks/useChat.ts` — assistant message gains a `groundedLines: (string|undefined)[]`
overlay alongside the raw `content`:

- `{token}` → append to `content` as today.
- `{line_done: {index, text}}` → `groundedLines[index] = text`.
- `{done}` → set `content = answer`, mark stream complete (render as today).

`_components/chat/ChatMessage.tsx` — compute `displayContent`:

- stream complete → `msg.content` (canonical), exactly as today.
- streaming → per line `i`: `groundedLines[i] ?? stripCitations(rawLine_i)`. Grounded
  lines show correct chips; not-yet-grounded lines show prose with chips **stripped**.
  Feed the joined `displayContent` into the existing `ReactMarkdown` + `withCitations`
  path (no new render pipeline).

`stripCitations` already exists in `_citation_parse.ts`.

### 4. Reconciliation trade-off (accepted)

Common case (bullet/prose answers): **zero flicker** — `feed_line` output equals the
canonical `finalize` output.

Two rare cases are smoothed only at `{done}` (frontend swaps to canonical `answer`):

1. **Summary section** — chips that appeared live in a recap line may be stripped at
   `done` when there are multiple "Zusammenfassung/Summary" headings (incremental
   `in_summary` triggers on the first-after-cited-body; canonical strips from the last).
2. **Table-header at the streaming tip** — the one-line lookahead isn't available yet
   for the very last streamed line; canonical fixes it.

Decision: reconcile these at `done` rather than chase live perfection. Accepted for the
experiment.

### 5. Edge cases

- **Abort mid-stream**: grounded lines already received stay; the existing abort path
  saves the fully-resolved partial `answer` (unchanged).
- **Error**: `{error}` path unchanged.
- **Reload of history**: persisted message holds the canonical answer (unchanged), so
  no `line_done` replay needed — history renders as today.

### 6. Testing

- **Parity (must hold):** `CitationGrounder.finalize(text)` is byte-identical to the
  current batch pipeline output for the existing `test_citation_*` fixtures.
- **Incremental parity:** feeding the same answer line-by-line via `feed_line` yields
  the same result as `finalize`, except the two §4 cases (asserted as known
  divergences).
- Frontend unit: `displayContent` overlay — grounded lines show chips, ungrounded lines
  are chip-free; `done` switches to canonical.

## Out of scope

- The source-list chips (`source_qmap`, the `[1] file.pdf` footer) — already
  retrieval-derived and stable; untouched.
- Highlight drawing logic in `viewer/_highlight.ts` — untouched.
- No new LLM calls.

## Rollback

Single feature branch. Discard = drop the `CitationGrounder`, the `line_done` event,
and the frontend overlay; the post-stream batch grounding remains exactly as today.
