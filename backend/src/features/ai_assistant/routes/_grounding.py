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
    registry: {chunk_id: {...}} for the model's CHUNK-id citations (see _chunk_cite).
    """

    def __init__(self, sources: dict, loader, source_qmap: list, registry: dict | None = None) -> None:
        self._sources = sources
        self._loader = loader
        self._qmap = source_qmap
        self._registry = registry or {}
        self._in_summary = False
        self._seen_cited_body = False

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
            return resolved
        resolved = fill_uncited_lines(resolved, self._sources, self._loader)
        if _CITE_RESOLVE_RE.search(resolved):
            self._seen_cited_body = True
        return resolved
