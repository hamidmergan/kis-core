"""Post-hoc citation: searches the spot for every answer line and sets the chips."""

import time

from loguru import logger

from src import database as db
from src.features.ai_assistant.prompts.refusal_prompts import (
    is_gap_line,
    refusal_reference_texts,
)

from ._chips import _needs_attribution
from ._evidence import (
    _ATTRIB_CANDIDATES,
    _attribute_generic_text,
    _attribution_subunits,
    _parallel_search,
)
from ._refusal import _refusal_lines


def run_attribution(text: str, *, prewarmer, provider, workspace_id: int,
                    source_ids, seen_pages_by_source, source_id_to_qnum: dict,
                    chunks: list[dict], transcript_by_source: dict,
                    scope_chunks, gap_sentence: str, intent: str,
                    umformen: bool) -> str:
    """Hangs a source chip on every backed line of the finished answer."""
    # Embed all lines in one call, the model refusals ride along.
    _cands = [ln for ln in text.split("\n") if _needs_attribution(ln)]
    # The sub-parts ride in the same batch too, one by one would be too expensive.
    _extra_units: list[str] = []
    for _ln in _cands:
        for _u in _attribution_subunits(_ln):
            if _u not in _cands and _u not in _extra_units:
                _extra_units.append(_u)
    _batch_lines = _cands + _extra_units
    _sentinels = refusal_reference_texts()
    # Reuses the warmed-up results and embeds only the missing ones.
    _pw_vecs = prewarmer.vecs if prewarmer is not None else {}
    _pw_hits = prewarmer.hits if prewarmer is not None else {}
    _vec_by_line: dict[str, list] = {ln: _pw_vecs[ln] for ln in _batch_lines if ln in _pw_vecs}
    _sentinel_vecs: list = []
    _embed_s = 0.0
    _embed_down = False
    _n_prewarmed = len(_vec_by_line)
    _miss_lines = [ln for ln in _batch_lines if ln not in _vec_by_line]
    _to_embed = _miss_lines + _sentinels
    if _to_embed:
        try:
            logger.info("post-hoc attribution: embedding {} lines ({} prewarmed of {}) + {} sentinels", len(_miss_lines), _n_prewarmed, len(_batch_lines), len(_sentinels))
            _t_embed0 = time.perf_counter()
            _vecs = provider.embed(_to_embed)
            _embed_s = time.perf_counter() - _t_embed0
            if len(_vecs) == len(_to_embed):
                for _ln, _v in zip(_miss_lines, _vecs[:len(_miss_lines)]):
                    _vec_by_line[_ln] = _v
                _sentinel_vecs = _vecs[len(_miss_lines):]
        except Exception as e:
            # If the batch fails there is no per-line retry, then simply no chip.
            _embed_down = True
            logger.warning("post-hoc batch embedding failed, answer ships without chips: {}", e)
    # The refusal sentence is matched verbatim, by distance it sits too close to a claim.
    _refusals = _refusal_lines(_cands, _vec_by_line, _sentinel_vecs)
    _refusals |= {ln for ln in _cands if is_gap_line(ln)}
    if gap_sentence:
        _refusals |= {ln for ln in _cands if gap_sentence in ln}
    if _refusals:
        logger.info("post-hoc attribution: {} refusal line(s) excluded from citation", len(_refusals))

    def _raw_search(_line: str):
        if _embed_down and _line not in _vec_by_line:
            return []
        try:
            _qv = _vec_by_line.get(_line) or provider.embed_one(_line)
            # The restriction to seen pages sits in the query, not as a filter behind it.
            return db.hybrid_search_chunks(workspace_id, _line, _qv,
                                           source_ids=source_ids,
                                           limit=_ATTRIB_CANDIDATES,
                                           seen_pages=seen_pages_by_source)
        except Exception as e:
            logger.warning("post-hoc attribution search failed for a line: {}", e)
            return []

    # All line searches run in parallel up front, the pass below only looks them up.
    _t_search0 = time.perf_counter()
    _hits_by_line: dict = {ln: _pw_hits[ln] for ln in _batch_lines if ln in _pw_hits}
    _search_miss = [ln for ln in _batch_lines if ln not in _hits_by_line]
    if _search_miss:
        _hits_by_line.update(_parallel_search(_search_miss, _raw_search))
    _search_s = time.perf_counter() - _t_search0

    def _search_one(_line: str):
        if _line in _hits_by_line:
            return _hits_by_line[_line]
        return _raw_search(_line)

    # Looking up a number beats sorting by meaning.
    _literal_cache: dict = {}

    def _literal_lookup(_figure: str):
        if _figure not in _literal_cache:
            try:
                _literal_cache[_figure] = db.find_chunks_containing(
                    workspace_id, _figure, source_ids=source_ids)
            except Exception as e:
                logger.warning("literal citation lookup failed for {}: {}", _figure, e)
                _literal_cache[_figure] = []
        return _literal_cache[_figure]

    _attr_result = _attribute_generic_text(text, _search_one, source_id_to_qnum,
                                   # Chips may only point at pages the model really saw.
                                   seen_pages_by_source=seen_pages_by_source,
                                   # In the overview the loose chip is dropped, a reshaping is never an overview.
                                   overview=(intent == "GENERIC" and not scope_chunks
                                             and not umformen),
                                   # The verbatim match sees exactly what the model read.
                                   context_chunks=chunks,
                                   # Who states this figure? Looked up, not ranked.
                                   literal_lookup=_literal_lookup,
                                   # Refusal lines never get a chip.
                                   refusal_lines=_refusals,
                                   # An explicit reference brackets the citations to the named spots.
                                   scope_chunks=scope_chunks,
                                   # The same Whisper segments make the media chip point at the right segment.
                                   transcript_by_source=transcript_by_source)
    _pw_flushes = prewarmer.flushes if prewarmer is not None else 0
    logger.info(
        "post-hoc attribution timing: embed {:.1f}s ({}/{} lines prewarmed in "
        "{} stream-embed calls) + search {:.1f}s ({} searched inline) over {} "
        "lines ({} candidates)",
        _embed_s, _n_prewarmed, len(_batch_lines), _pw_flushes, _search_s,
        len(_search_miss), len(_hits_by_line), len(_cands))
    return _attr_result
