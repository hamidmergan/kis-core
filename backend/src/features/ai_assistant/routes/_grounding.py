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
