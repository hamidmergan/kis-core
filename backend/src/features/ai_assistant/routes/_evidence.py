"""Finds the chunk that backs a line and hangs the chips into the answer."""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from loguru import logger

from src.services.aia_literal_evidence import names_line_verbatim, pin_words

from ._chips import (
    _attach_chips,
    _attr_blocks,
    _attribution_chip,
    _is_prose_line,
    _lead_in_lines,
    _needs_attribution,
    _place_chip,
)
from ._text import (
    _clauses,
    _is_table_delim,
    _is_table_row,
    _is_toc_chunk,
    _significant_tokens,
    _split_sentences,
)


# Overview answers are backed afterwards by search, with a distance threshold.
_GENERIC_ATTRIB_MAX_DIST = 0.6


# Looser threshold so no line of a backed answer stays without a chip.
_GUARANTEE_MAX_DIST = 0.85


# How many candidates the search must return before picking.
_ATTRIB_CANDIDATES = 40


_MAX_CHIPS_PER_LINE = 3


# A further chip only comes along when its distance is practically that of the best.
_MULTI_CHIP_MAX_DELTA = 0.04


# Ceiling of chips per chip position, matching the display in the browser.
_COVERAGE_MAX_CHIPS_PER_LINE = 3


# How many looked-up chunks may push ahead per line.
_MAX_LITERAL_CANDIDATES = 4


def _is_seen(chunk: dict, seen_pages_by_source: Optional[dict]) -> bool:
    """True when source and page of this chunk really were in the model's context."""
    if seen_pages_by_source is None:
        return True
    pages = seen_pages_by_source.get(chunk.get("source_id"))
    if pages is None:
        return False
    if chunk.get("start_time") is not None:   # media: source-level cross-check (no page)
        return True
    pg = chunk.get("page_number")
    return pg is None or pg in pages


def _scope_chunk_ids(scope_chunks: Optional[list[dict]]) -> Optional[set]:
    """The chunk ids the model saw when a page or time reference was explicit."""
    if not scope_chunks:
        return None
    ids = {c["id"] for c in scope_chunks if c.get("id") is not None}
    return ids or None


def _in_scope(chunk: dict, scope_ids: Optional[set]) -> bool:
    """True when the chunk lies inside the explicit reference window, or there is none."""
    return scope_ids is None or chunk.get("id") in scope_ids


def _pick_attribution(hits: list[dict], max_distance: float,
                      seen_pages_by_source: Optional[dict] = None) -> Optional[dict]:
    """The nearest hit within the threshold, otherwise None and therefore no chip."""
    cand = [h for h in hits
            if h.get("vec_distance") is not None
            and not _is_toc_chunk(h.get("content") or "")
            and _is_seen(h, seen_pages_by_source)]
    if not cand:
        return None
    best = min(cand, key=lambda h: h["vec_distance"])
    return best if best["vec_distance"] <= max_distance else None


def _exact_attribution_chunk(line: str, context_chunks: list[dict]) -> Optional[dict]:
    """Backs a line by its verbatim occurrence in a chunk that was already fetched."""
    toks = _significant_tokens(line)
    if not toks:
        return None
    for c in context_chunks:
        content = (c.get("content") or "")
        if _is_toc_chunk(content):
            continue
        low = content.lower()
        if all(t in low for t in toks):
            return c
    return None


# Split on comma and semicolon only, content words from four characters count.
_CONTENT_WORD_RE = re.compile(r"[^\W\d_]{4,}", re.UNICODE)


def _content_words(text: str) -> set:
    return {w.casefold() for w in _CONTENT_WORD_RE.findall(text or "")}


def _figure_first(unit: str, cands: list[dict],
                  corpus: Optional[list[str]] = None) -> list[dict]:
    """Candidates that name a number of the line verbatim come first."""
    if not cands or not corpus:
        return cands
    from src.services.aia_literal_evidence import distinctive_tokens, figure_runs
    _, zahlen = distinctive_tokens(unit, corpus)
    if not zahlen:
        return cands
    vorne, hinten = [], []
    for c in cands:
        ziel = vorne if zahlen & figure_runs(c.get("content") or "") else hinten
        ziel.append(c)
    return vorne + hinten


def _extra_chip_earns_place(unit: str, primary: dict, extra: dict,
                            pins: frozenset = frozenset(),
                            corpus: Optional[list[str]] = None) -> bool:
    """Whether an extra chip earns its place next to the best hit."""
    from src.services.aia_literal_evidence import distinctive_tokens, figure_runs
    if corpus:
        _, zahlen = distinctive_tokens(unit, corpus)
        traegt_extra = figure_runs(extra.get("content") or "")
        traegt_primary = figure_runs(primary.get("content") or "")
        if any(z in traegt_extra and z not in traegt_primary for z in zahlen):
            return True
    if pins:
        from src.services.aia_literal_evidence import carries_pin
        fehlend = {p for p in pins if not carries_pin(p, primary.get("content") or "")}
        if not fehlend:
            return False
        return any(carries_pin(p, extra.get("content") or "") for p in fehlend)
    if primary.get("source_id") != extra.get("source_id"):
        return True
    unit_words = _content_words(unit)
    if not unit_words:
        return True
    new_words = unit_words & _content_words(extra.get("content") or "")
    return bool(new_words - _content_words(primary.get("content") or ""))


def _literal_candidates(line: str, literal_lookup, corpus: Optional[list[str]],
                        seen_pages_by_source: Optional[dict],
                        scope_ids: Optional[set]) -> list[dict]:
    """Chunks that carry a distinguishing number of the line verbatim."""
    if literal_lookup is None:
        return []
    from src.services.aia_literal_evidence import lookup_figures
    best: dict = {}
    for fig in lookup_figures(line, corpus or []):
        hits = literal_lookup(fig) or []
        for h in hits:
            cid = h.get("id")
            if _is_toc_chunk(h.get("content") or ""):
                continue
            if not _is_seen(h, seen_pages_by_source) or not _in_scope(h, scope_ids):
                continue
            # The rarest hit wins, a common date says little.
            if cid not in best or len(hits) < best[cid][0]:
                best[cid] = (len(hits), dict(h))
    ordered = sorted(best.values(), key=lambda pair: pair[0])
    return [h for _, h in ordered][:_MAX_LITERAL_CANDIDATES]


def _line_candidates(line: str, search_one, context_chunks: Optional[list[dict]],
                     seen_pages_by_source: Optional[dict],
                     scope_ids: Optional[set] = None,
                     literal_lookup=None, corpus: Optional[list[str]] = None) -> list[dict]:
    """Fetched chunks that could back the line, nearest first."""
    exact = _exact_attribution_chunk(line, context_chunks) if context_chunks else None
    if (exact is not None and _is_seen(exact, seen_pages_by_source)
            and _in_scope(exact, scope_ids)):
        e = dict(exact)
        e["vec_distance"] = 0.0  # verbatim presence == certain
        return [e]               # the verbatim chunk is the sole answer
    cands = []
    for h in (search_one(line) or []):
        if (h.get("vec_distance") is None
                or _is_toc_chunk(h.get("content") or "")
                or not _is_seen(h, seen_pages_by_source)
                or not _in_scope(h, scope_ids)):
            continue
        cands.append(h)
    cands.sort(key=lambda h: h["vec_distance"])
    # The chunk with the number moves right behind the nearest one.
    found = _literal_candidates(line, literal_lookup, corpus, seen_pages_by_source, scope_ids)
    if found:
        lit_ids = {h.get("id") for h in found if h.get("id") is not None}
        known = {c.get("id") for c in cands}
        rank = {h.get("id"): i for i, h in enumerate(found)}
        promoted = sorted([c for c in cands[1:] if c.get("id") in lit_ids],
                          key=lambda c: rank.get(c.get("id"), 99))
        others = [c for c in cands[1:] if c.get("id") not in lit_ids]
        fresh = [h for h in found if h.get("id") not in known]
        anchor = cands[0]["vec_distance"] if cands else _GENERIC_ATTRIB_MAX_DIST / 2
        for i, h in enumerate(fresh):
            h["vec_distance"] = anchor + 1e-6 * (i + 1)   # never a real distance: unranked
        for h in promoted + fresh:
            h["literal"] = True
        cands = cands[:1] + promoted + fresh + others
    return cands


def _chips_for_line(cands: list[dict], source_id_to_qnum: dict,
                    max_distance: float,
                    guarantee_dist: float = _GUARANTEE_MAX_DIST,
                    line: str = "", corpus: Optional[list[str]] = None,
                    transcript_by_source: Optional[dict[int, list[dict]]] = None) -> list[str]:
    """Builds the chips of a line: the best hit plus only practically equally near ones."""
    from src.services.aia_literal_evidence import carries_pin, pin_words
    chips: list[str] = []
    keys: set = set()
    primary_d: Optional[float] = None
    primary_content = ""
    evidence_corpus = corpus or [c.get("content") or "" for c in cands]
    # Every further chip must carry a word the best hit is missing.
    pins = pin_words(line, evidence_corpus) if line else set()
    for h in cands:
        qnum = source_id_to_qnum.get(h.get("source_id"))
        if qnum is None:
            continue
        d = h.get("vec_distance")
        d = 1.0 if d is None else d
        if primary_d is None:
            if d > guarantee_dist:  # closest seen chunk too far → no chip at all
                break
            primary_d = d                # the guarantee chip; anchors the relative gate
            primary_content = h.get("content") or ""
            pins = {p for p in pins if carries_pin(p, primary_content)}
        elif d > max_distance:
            break                        # off topic for everyone, evidence or not
        elif h.get("literal"):
            pass                         # names the statement's number verbatim, that IS the spot
        elif d > primary_d + _MULTI_CHIP_MAX_DELTA:
            continue                     # noticeably farther off than the best hit
        elif pins and not any(carries_pin(p, h.get("content") or "") for p in pins):
            continue                     # backs only the topic, not the statement
        c = _attribution_chip(qnum, h, line,
                              (transcript_by_source or {}).get(h.get("source_id")))
        if not c:
            continue
        # The finished chip is the key, it already carries source and target.
        if c[0] in keys:
            continue
        chips.extend(c)
        keys.add(c[0])
        if len(chips) >= _MAX_CHIPS_PER_LINE:
            break
    return chips


def _holds_for_every_sentence(text: str, predicate) -> bool:
    """Whether a condition holds for every sentence of the text."""
    sents = _split_sentences(text) or [text]
    return all(predicate(s) for s in sents)


def _attribution_subunits(line: str) -> list[str]:
    """The sub-units of a line that are embedded along up front."""
    if _is_prose_line(line):
        sents = _split_sentences(line)
        if len(sents) > 1:
            out: list[str] = []
            for s in sents:
                if s != line and s not in out:
                    out.append(s)
                for cl in _clauses(s):
                    if cl != line and cl not in out:
                        out.append(cl)
            return out
    return _clauses(line)


_PAREN_RE = re.compile(r"\(([^)]{1,80})\)")


# A statute abbreviation, all caps or with an inner capital.
_LAW_ABBR_RE = re.compile(r"[A-ZÄÖÜ]{2,}[0-9]*|[A-ZÄÖÜ][A-Za-zäöüß0-9]*[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9]*")


def _names_many_laws(text: str, threshold: int = 3) -> bool:
    """True when a line names many statute abbreviations and therefore has no single source."""
    abbrs: set = set()
    for m in _PAREN_RE.finditer(text or ""):
        abbrs.update(_LAW_ABBR_RE.findall(m.group(1)))
    return len(abbrs) >= threshold


# A spelled-out enumeration of at least four capitalised single words.
_CAP_TOKEN = r"[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9-]+"


_ENUM_LIST_RE = re.compile(rf"{_CAP_TOKEN}(?:\s*,\s*{_CAP_TOKEN}){{3,}}")


_ENUM_BACKED_MIN = 0.5  # fraction of items the cited chunk must contain to keep the chip


def _enum_chip_unbacked(text: str, content: str) -> bool:
    """True when a long enumeration does not occur in the cited chunk at all."""
    m = _ENUM_LIST_RE.search(text or "")
    if not m:
        return False
    items = [t.strip() for t in m.group(0).split(",")]
    if len(items) < 4:
        return False
    low = (content or "").lower()
    present = sum(1 for it in items if it.lower() in low)
    return present < len(items) * _ENUM_BACKED_MIN


def _attribute_prose_line(sentences: list[str], search_one, source_id_to_qnum: dict, *,
                          context_chunks, seen_pages_by_source, scope_ids,
                          max_distance: float, guarantee: float, overview: bool,
                          literal_lookup=None, transcript_by_source=None) -> str:
    """Rebuilds a paragraph with a source chip after every sentence."""
    corpus = [c.get("content") or "" for c in (context_chunks or [])] or None
    parts: list[str] = []
    for sent in sentences:
        chips: list[str] = []
        if _needs_attribution(sent) and not (overview and _names_many_laws(sent)):
            cands = _line_candidates(sent, search_one, context_chunks,
                                     seen_pages_by_source, scope_ids,
                                     literal_lookup=literal_lookup, corpus=corpus)
            satz_pins = frozenset(pin_words(sent, corpus or
                                            [c.get("content") or "" for c in cands]))
            if cands and not (overview and _enum_chip_unbacked(sent, cands[0].get("content") or "")):
                chips = _chips_for_line(cands, source_id_to_qnum, max_distance,
                                        guarantee_dist=guarantee, line=sent, corpus=corpus,
                                        transcript_by_source=transcript_by_source)
                seen_targets = set(chips)
                for cl in _clauses(sent):
                    if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                        break            # full, else the clause appends a fourth
                    ccands = _figure_first(sent, _line_candidates(
                        cl, search_one, context_chunks, seen_pages_by_source, scope_ids,
                        literal_lookup=literal_lookup, corpus=corpus), corpus)
                    cchips = _chips_for_line(ccands, source_id_to_qnum, max_distance,
                                             guarantee_dist=guarantee, line=cl,
                                             corpus=corpus,
                                             transcript_by_source=transcript_by_source) if ccands else []
                    # An extra chip only stays when it covers a word of the sentence that was missing.
                    if (cchips and cchips[0] not in seen_targets
                            and _extra_chip_earns_place(sent, cands[0], ccands[0],
                                                        satz_pins, corpus=corpus)):
                        chips.append(cchips[0])
                        seen_targets.add(cchips[0])
                        if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                            break
        parts.append(_attach_chips(sent, " ".join(chips)) if chips else sent)
    return " ".join(parts)


# The searches run over a thread pool, otherwise the pause after the answer bites.
_ATTRIB_SEARCH_CONCURRENCY = 8


def _parallel_search(lines: list[str], search_fn: Callable[[str], list],
                     max_workers: int = _ATTRIB_SEARCH_CONCURRENCY) -> dict[str, list]:
    """Searches once per distinct line over a thread pool."""
    uniq = [ln for ln in dict.fromkeys(lines) if ln and ln.strip()]
    if not uniq:
        return {}

    def _one(ln: str) -> list:
        try:
            return search_fn(ln) or []
        except Exception as e:  # mirror _search_one: a failed search is just "no hits"
            logger.warning("parallel attribution search failed for a line: {}", e)
            return []

    with ThreadPoolExecutor(max_workers=min(max_workers, len(uniq))) as ex:
        results = list(ex.map(_one, uniq))
    return dict(zip(uniq, results))


class _AttributionPrewarmer:
    """Warms the evidence caches while the answer is still streaming."""

    def __init__(self, embed_batch: Callable[[list], list],
                 search_with_vec: Callable[[str, Optional[list]], list]):
        # embed_batch embeds the whole batch in one call, search_with_vec searches with it.
        self._embed_batch = embed_batch
        self._search_with_vec = search_with_vec
        self.vecs: dict[str, list] = {}
        self.hits: dict[str, list] = {}
        self.flushes = 0            # embed calls actually spent (visibility for the rate budget)
        self._seen: set[str] = set()
        self._pending: list[str] = []
        self._lock = asyncio.Lock()

    def feed_line(self, line: str) -> None:
        """Queues a finished answer line with its sub-units for warming."""
        if not line or not _needs_attribution(line):
            return
        for unit in [line, *_attribution_subunits(line)]:
            if unit and unit.strip() and unit not in self._seen:
                self._seen.add(unit)
                self._pending.append(unit)

    def pending_count(self) -> int:
        return len(self._pending)

    async def flush(self) -> None:
        """Embeds and searches whatever is queued, exactly one run at a time."""
        async with self._lock:
            batch = self._pending
            self._pending = []
            if not batch:
                return
            try:
                vecs = await asyncio.to_thread(self._embed_batch, batch)
            except Exception as e:
                logger.warning("attribution prewarm embed failed (recomputed at attribution): {}", e)
                return
            if not vecs or len(vecs) != len(batch):
                return
            self.flushes += 1
            for unit, vec in zip(batch, vecs):
                self.vecs[unit] = vec
            searched = await asyncio.to_thread(
                _parallel_search, batch,
                lambda ln: self._search_with_vec(ln, self.vecs.get(ln)))
            self.hits.update(searched)


def _attribute_generic_text(text: str, search_one, source_id_to_qnum: dict, offset_fn=None, *,
                            seen_pages_by_source=None, context_chunks=None, overview: bool = False,
                            max_distance: float = _GENERIC_ATTRIB_MAX_DIST,
                            refusal_lines: Optional[set] = None,
                            scope_chunks: Optional[list[dict]] = None,
                            literal_lookup=None,
                            transcript_by_source: Optional[dict[int, list[dict]]] = None) -> str:
    """Backs every content-bearing line of an overview answer after the fact."""
    lines = text.split("\n")
    # The lead-in of an overview talks about the whole material, no single spot backs it.
    lead_in = _lead_in_lines(lines) if overview else set()
    # An explicit page or time reference brackets the evidence.
    scope_ids = _scope_chunk_ids(scope_chunks)
    # Measured against everything the answer was written from.
    evidence_corpus = [c.get("content") or "" for c in (context_chunks or [])] or None
    # Pass 1 collects the candidates per line and per clause.
    cand_by_idx: dict[int, list[dict]] = {}
    clause_cands_by_idx: dict[int, list[list[dict]]] = {}
    grounded = False
    # In the overview the tight threshold applies, a statute list stays chip free.
    guarantee = max_distance if overview else _GUARANTEE_MAX_DIST
    for i, line in enumerate(lines):
        if i in lead_in or not _needs_attribution(line):
            continue
        # A refusal is not a claim and never gets evidence.
        if refusal_lines and line in refusal_lines:
            continue
        # A table header row is a column label and is never backed.
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if _is_table_row(line) and _is_table_delim(nxt):
            continue
        cands = _line_candidates(line, search_one, context_chunks, seen_pages_by_source,
                                 scope_ids, literal_lookup=literal_lookup,
                                 corpus=evidence_corpus)
        if not cands:
            continue
        cand_by_idx[i] = cands
        d0 = cands[0].get("vec_distance")
        if d0 is not None and d0 <= max_distance:
            grounded = True
        # A short answer sits far from any chunk by meaning, but its spot names it verbatim.
        elif (d0 is not None and d0 <= guarantee
              and names_line_verbatim(line, cands[0].get("content") or "", evidence_corpus or [])):
            grounded = True
        cc = [c for c in (_line_candidates(cl, search_one, context_chunks,
                                           seen_pages_by_source, scope_ids,
                                           literal_lookup=literal_lookup,
                                           corpus=evidence_corpus)
                          for cl in _clauses(line)) if c]
        if cc:
            clause_cands_by_idx[i] = cc
    # Pass 2 puts the chips at the block end, sources deduplicated across the block.
    out = list(lines)
    if grounded:
        # Chips are not deduplicated across blocks, two claims may name the same spot.
        for blk in _attr_blocks(lines):
            if blk[0] in lead_in:
                continue
            # A prose block gets its chips per sentence instead of once at the end.
            if _is_prose_line(lines[blk[0]]):
                for _i in blk:
                    if refusal_lines and lines[_i] in refusal_lines:
                        continue
                    _sents = _split_sentences(lines[_i])
                    if _sents:
                        out[_i] = _attribute_prose_line(
                            _sents, search_one, source_id_to_qnum,
                            context_chunks=context_chunks, seen_pages_by_source=seen_pages_by_source,
                            scope_ids=scope_ids, max_distance=max_distance,
                            guarantee=guarantee, overview=overview,
                            literal_lookup=literal_lookup,
                            transcript_by_source=transcript_by_source)
                continue
            block_text = " ".join(lines[i] for i in blk)
            if overview and _holds_for_every_sentence(block_text, _names_many_laws):
                continue
            agg: list[dict] = []
            for idx in blk:
                agg.extend(cand_by_idx.get(idx, []))
            if not agg:
                continue
            agg.sort(key=lambda h: h["vec_distance"] if h.get("vec_distance") is not None else 1.0)
            # In the overview an enumeration whose evidence carries only one item stays chip free.
            _cited = agg[0].get("content") or ""
            if overview and _holds_for_every_sentence(
                    block_text, lambda s: _enum_chip_unbacked(s, _cited)):
                continue
            chips = _chips_for_line(agg, source_id_to_qnum, max_distance,
                                    guarantee_dist=guarantee, line=block_text,
                                    corpus=evidence_corpus,
                                    transcript_by_source=transcript_by_source)
            # One coverage chip per clause so every fact gets a reference.
            if not _is_table_row(lines[blk[-1]]):
                seen_targets = set(chips)
                for idx in blk:
                    for ccands in clause_cands_by_idx.get(idx, []):
                        if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                            break        # full, else the clause appends a fourth
                        ccands = _figure_first(block_text, ccands, evidence_corpus)
                        cchips = _chips_for_line(ccands, source_id_to_qnum, max_distance,
                                                 guarantee_dist=guarantee, line=block_text,
                                                 corpus=evidence_corpus,
                                                 transcript_by_source=transcript_by_source)
                        # Here too an extra chip must cover something the best hit does not carry.
                        if (cchips and cchips[0] not in seen_targets
                                and _extra_chip_earns_place(block_text, agg[0], ccands[0],
                                                            corpus=evidence_corpus)):
                            chips.append(cchips[0])
                            seen_targets.add(cchips[0])
                            if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                                break
                    if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                        break
            if chips:
                last = blk[-1]
                # In a table row the chip goes into the last cell, otherwise at the block end.
                out[last] = _place_chip(lines[last], " ".join(chips))
    return "\n".join(out)
