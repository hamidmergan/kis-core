"""Per-line incremental citation grounding for the streaming chat answer.

Reuses the exact per-line functions the post-stream batch path uses
(`resolve_citation_positions`, `fill_uncited_lines`), plus the summary-strip rule,
so a line grounded live equals what the canonical pipeline produces — except the two
edge cases documented in the spec (multi summary headings, table header at the
streaming tip), which the final `done` event reconciles.
"""
from __future__ import annotations

import re

from ._chunk_cite import resolve_chunk_refs
from ._helpers import (
    _CITE_RESOLVE_RE,
    _SUMMARY_HEADING_RE,
    _chipify_inline_refs,
    _dedup_line_chips,
    _sanitize_citations,
    _strip_title_line_chips,
    _strip_chunk_id_leak,
    _nav_only_chips,
    fill_uncited_lines,
    resolve_citation_positions,
)


class CitationGrounder:
    """Grounds one answer line at a time, carrying summary state across lines.

    sources: {qnum: {"source": row, "is_media": bool, "pages": set}} (coverage shape)
    loader:  SourceUnitLoader (or a stub exposing .units / optional .offset_suffixes /
             .furniture).
    source_qmap: the [{qnum, uuid, filename, is_media}] list (for _chipify_inline_refs).
    registry: {chunk_id: {...}} for the model's CHUNK-id citations (see _chunk_cite).
    """

    def __init__(self, sources: dict, loader, source_qmap: list, registry: dict | None = None,
                 *, fill: bool = True, nav_only: bool = False) -> None:
        self._sources = sources
        self._loader = loader
        self._qmap = source_qmap
        self._registry = registry or {}
        self._in_summary = False
        self._seen_cited_body = False
        # When False, skip the uncited-line filler. Used for page-scoped summaries:
        # the whole answer is one named page, so filling per line grounds against the
        # WHOLE document and scatters chips across unrelated pages (a TOC page is the
        # worst case). Model/chunk-id citations are still resolved.
        self._fill = fill
        # When True, reduce chips to page/timestamp only (no highlight) — for a
        # multi-page/-chunk scoped summary, where a span highlight would light up many
        # blocks across pages. Click then just scrolls to the page. See _nav_only_chips.
        self._nav_only = nav_only

    def feed_line(self, line: str) -> str:
        line = _sanitize_citations(line)
        line = _chipify_inline_refs(line, self._qmap)
        # NOTE: triggers on the FIRST summary heading; the batch path
        # (_strip_summary_citations) uses the LAST. Divergence only matters with
        # multiple summary headings — reconciled by the final `done` event (see spec).
        if _SUMMARY_HEADING_RE.match(line):
            self._in_summary = True
        # The model cites the CHUNK it used (`[N, #C | kw]`); resolve those to verified
        # real page/timestamp chips FIRST. When this line carried a chunk-id citation we
        # trust it (authoritative) and skip the legacy keyword resolver; otherwise fall
        # back to it for old-format / uncited lines.
        had_chunk_ref, line = resolve_chunk_refs(line, self._registry, self._loader)
        resolved = line if had_chunk_ref else resolve_citation_positions(line, self._sources, self._loader)
        if self._in_summary:
            # Mirror _strip_summary_citations: only strip once a cited body has
            # preceded the heading; otherwise this is a summary-style TITLE and we
            # leave the (resolved) chips. Summary lines never get fill (matches the
            # in_summary gate inside fill_uncited_lines).
            if self._seen_cited_body:
                resolved = _CITE_RESOLVE_RE.sub("", resolved)
                resolved = re.sub(r"[ \t]+([.,;:!?])", r"\1", resolved)
                resolved = re.sub(r"[ \t]{2,}", " ", resolved).rstrip()
            resolved = _strip_title_line_chips(_dedup_line_chips(resolved))
            if self._nav_only:
                resolved = _nav_only_chips(resolved)
            return _strip_chunk_id_leak(resolved)
        if self._fill:
            resolved = fill_uncited_lines(resolved, self._sources, self._loader)
        # Drop a chip that points to the same source+position as another on this line
        # (model/filler can both land on the identical spot) -> never show it twice.
        resolved = _dedup_line_chips(resolved)
        # A bold-only section title is a heading, not a claim: strip any chip on it
        # (model-emitted or filler-appended) so a title line never carries a citation.
        resolved = _strip_title_line_chips(resolved)
        # Nav-only AFTER fill, so filler-added chips are reduced to page/timestamp too.
        if self._nav_only:
            resolved = _nav_only_chips(resolved)
        # Drop a trailing meta-clause leaking an internal chunk/source id (#<digit>).
        resolved = _strip_chunk_id_leak(resolved)
        if _CITE_RESOLVE_RE.search(resolved):
            self._seen_cited_body = True
        return resolved
