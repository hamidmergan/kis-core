"""Tests for the two RAG chat paths: GENERIC (overview, single wide retrieval)
and SPECIFIC (topic-focused, hybrid search). Both are pgvector-only — no
summaries are precomputed at upload.

Covers the routing decision, the generic single-search retrieval (merge/dedup +
source diversity), the specific source-diversity reordering, and the async LLM
helpers — all the logic that decides WHICH context the tutor sees before it
ever writes a citation.

LLM and DB are faked/monkeypatched so these are deterministic and offline.
"""
import pytest

from src.features.ai_assistant.routes import chat as chat_mod
from src.features.ai_assistant.routes.chat import (
    _should_skip_intent_classification,
    _sample,
    _retrieve_generic_context,
    _full_context_if_fits,
    _context_budget,
    _diversify_by_source,
    _order_round_robin,
    _classify_intent,
    _understand_query,
    _parse_understanding,
    _stream_usage_tokens,
    _enrich_chat_trace,
    _pack_context_batches,
    _expand_with_neighbors,
    _INTENT_MAX_WORDS,
)


# ── fake LLM matching the openai-style client surface the helpers call ───────

class _Msg:
    def __init__(self, content, reasoning=None):
        self.content = content
        if reasoning is not None:
            self.reasoning_content = reasoning


class _Resp:
    def __init__(self, content, reasoning=None):
        self.choices = [type("C", (), {"message": _Msg(content, reasoning)})()]


class _Completions:
    def __init__(self, content, reasoning, raise_exc):
        self._content, self._reasoning, self._raise = content, reasoning, raise_exc

    def create(self, **kw):
        if self._raise:
            raise RuntimeError("provider down")
        return _Resp(self._content, self._reasoning)


class _Client:
    def __init__(self, content, reasoning, raise_exc):
        self._args = (content, reasoning, raise_exc)

    def with_options(self, **kw):
        return self

    @property
    def chat(self):
        return type("Chat", (), {"completions": _Completions(*self._args)})()


class FakeLLM:
    def __init__(self, content="", reasoning=None, raise_exc=False):
        self._client = _Client(content, reasoning, raise_exc)
        self._model = "fake-model"
        self._extra_body = None


# ── routing: cheap pre-filter (no LLM round-trip) ────────────────────────────

def test_skip_intent_for_popup_source_text():
    # A popup action carries source_text -> always SPECIFIC, never classify.
    assert _should_skip_intent_classification("selected passage", [1, 2], "Was heißt das?") is True


def test_skip_intent_when_no_sources():
    assert _should_skip_intent_classification(None, [], "Worum geht es?") is True
    assert _should_skip_intent_classification(None, None, "Worum geht es?") is True


def test_skip_intent_for_long_question():
    long_q = " ".join(["wort"] * (_INTENT_MAX_WORDS + 1))
    assert _should_skip_intent_classification(None, [1], long_q) is True


def test_does_not_skip_for_short_question_with_sources():
    # Short question + real sources + no popup -> worth an LLM classification.
    assert _should_skip_intent_classification(None, [1, 2], "Worum geht es?") is False


# ── routing: LLM verdict parsing (provider faked) ────────────────────────────

@pytest.mark.asyncio
async def test_classify_intent_reads_generic():
    assert await _classify_intent(FakeLLM(content="GENERIC"), "Worum geht es?") == "GENERIC"


@pytest.mark.asyncio
async def test_classify_intent_defaults_specific_on_unknown():
    assert await _classify_intent(FakeLLM(content="banana"), "x") == "SPECIFIC"


@pytest.mark.asyncio
async def test_classify_intent_strips_think_block_and_punctuation():
    raw = "<think>hmm overview-ish</think>  'GENERIC.'"
    assert await _classify_intent(FakeLLM(content=raw), "x") == "GENERIC"


@pytest.mark.asyncio
async def test_classify_intent_falls_back_to_reasoning_content():
    # Some reasoning models leave content empty and put the verdict in reasoning.
    assert await _classify_intent(FakeLLM(content="", reasoning="GENERIC"), "x") == "GENERIC"


@pytest.mark.asyncio
async def test_classify_intent_defaults_specific_on_error():
    assert await _classify_intent(FakeLLM(raise_exc=True), "x") == "SPECIFIC"


# ── combined query understanding (intent + scope in ONE call) ────────────────

def test_parse_understanding_intent_and_page_scope():
    intent, scope = _parse_understanding(
        '{"intent":"GENERIC","scope":{"unit":"page","intervals":[[5,5]]}}')
    assert intent == "GENERIC"
    assert scope == {"unit": "page", "intervals": [[5, 5]]}


def test_parse_understanding_specific_no_scope():
    intent, scope = _parse_understanding(
        '{"intent":"SPECIFIC","scope":{"unit":null,"intervals":[]}}')
    assert intent == "SPECIFIC"
    assert scope == {"unit": None, "intervals": []}


def test_parse_understanding_strips_think_and_fences():
    raw = '<think>hmm</think>```json\n{"intent":"SPECIFIC","scope":{"unit":"time","intervals":[[10,10]]}}\n```'
    intent, scope = _parse_understanding(raw)
    assert intent == "SPECIFIC" and scope == {"unit": "time", "intervals": [[10, 10]]}


def test_parse_understanding_salvages_generic_from_broken_json():
    # braces present but invalid JSON -> still salvage the GENERIC token
    intent, scope = _parse_understanding("{intent: GENERIC, broken,}")
    assert intent == "GENERIC" and scope == {"unit": None, "intervals": []}


def test_parse_understanding_garbage_defaults_specific():
    intent, scope = _parse_understanding("no json at all")
    assert intent == "SPECIFIC" and scope == {"unit": None, "intervals": []}


@pytest.mark.asyncio
async def test_understand_query_reads_both():
    llm = FakeLLM(content='{"intent":"GENERIC","scope":{"unit":"page","intervals":[[12,14]]}}')
    intent, scope = await _understand_query(llm, "fasse Seite 12 bis 14 zusammen")
    assert intent == "GENERIC" and scope == {"unit": "page", "intervals": [[12, 14]]}


@pytest.mark.asyncio
async def test_understand_query_defaults_on_error():
    intent, scope = await _understand_query(FakeLLM(raise_exc=True), "x")
    assert intent == "SPECIFIC" and scope == {"unit": None, "intervals": []}


# ── _sample: even-spaced cap used in multi-source generic ────────────────────

def test_sample_returns_all_when_under_cap():
    assert _sample([1, 2, 3], 5) == [1, 2, 3]


def test_sample_caps_and_spreads_evenly():
    out = _sample(list(range(100)), 4)
    assert len(out) == 4
    assert out[0] == 0          # always includes the start
    assert out == sorted(out)   # preserves order
    assert len(set(out)) == 4   # no duplicates


# ── full-context-if-fits: skip retrieval when the doc fits the budget ────────

def test_full_context_returns_all_chunks_when_under_budget(monkeypatch):
    chunks = {1: [{"source_id": 1, "page_number": p, "content": "x" * 100} for p in range(5)]}
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: chunks.get(sid, []))
    out = _full_context_if_fits([1], max_chars=10_000)  # 5*100 = 500 << budget
    assert out is not None
    assert len(out) == 5
    assert [c["page_number"] for c in out] == [0, 1, 2, 3, 4]


def test_full_context_returns_none_when_over_budget(monkeypatch):
    # A "large doc": 50 chunks * 1000 chars = 50k, well over a tiny budget.
    chunks = {1: [{"source_id": 1, "page_number": p, "content": "x" * 1000} for p in range(50)]}
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: chunks.get(sid, []))
    assert _full_context_if_fits([1], max_chars=5_000) is None


def test_full_context_sums_across_multiple_sources(monkeypatch):
    # Each source fits alone, but together they exceed the budget -> retrieval.
    chunks = {
        1: [{"source_id": 1, "page_number": 1, "content": "x" * 3000}],
        2: [{"source_id": 2, "page_number": 1, "content": "x" * 3000}],
    }
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: chunks.get(sid, []))
    assert _full_context_if_fits([1], max_chars=5_000) is not None        # 3k < 5k
    assert _full_context_if_fits([1, 2], max_chars=5_000) is None         # 6k > 5k


def test_full_context_none_for_empty_sources(monkeypatch):
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: [])
    assert _full_context_if_fits([1], max_chars=10_000) is None


def test_context_budget_reads_setting_with_default(monkeypatch):
    monkeypatch.setattr(chat_mod.db, "get_setting", lambda key, default: "123456")
    assert _context_budget() == 123456
    # Bad value -> falls back to the tier-safe constant.
    monkeypatch.setattr(chat_mod.db, "get_setting", lambda key, default: "not-a-number")
    assert _context_budget() == chat_mod.AIA_CONTEXT_MAX_CHARS


def test_context_budget_clamps_oversized_setting(monkeypatch):
    # An admin typo / stale DB value above the hard cap is clamped on read so it
    # can never push a context the model cannot take.
    monkeypatch.setattr(chat_mod.db, "get_setting", lambda key, default: "1000000")
    assert _context_budget() == chat_mod.AIA_CONTEXT_HARD_CAP
    # Absurd 10M likewise clamps to the cap, never returned verbatim.
    monkeypatch.setattr(chat_mod.db, "get_setting", lambda key, default: "10000000")
    assert _context_budget() == chat_mod.AIA_CONTEXT_HARD_CAP
    # A sane value below the cap passes through untouched.
    monkeypatch.setattr(chat_mod.db, "get_setting", lambda key, default: "120000")
    assert _context_budget() == 120000


# ── generic path: single-search pgvector retrieval (db/provider monkeypatched) ──

class _FakeProvider:
    def embed_one(self, text):
        return [0.0, 0.0]


@pytest.mark.asyncio
async def test_generic_retrieval_runs_one_wide_search(monkeypatch):
    # No sub-query decomposition: a single source is retrieved with ONE wide
    # hybrid search at _GENERIC_RETRIEVE_LIMIT, not N per-query searches.
    calls = []
    def fake_search(wsid, term, vec, source_ids=None, limit=None):
        calls.append(limit)
        return [{"source_id": 1, "page_number": 1, "content": "c1"}]
    monkeypatch.setattr(chat_mod.db, "hybrid_search_chunks", fake_search)
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: [])
    await _retrieve_generic_context(_FakeProvider(), 99, [1], "Worum geht es?")
    assert calls == [chat_mod._GENERIC_RETRIEVE_LIMIT]


@pytest.mark.asyncio
async def test_generic_retrieval_merges_dedups_and_diversifies(monkeypatch):
    # The wide search may surface a chunk more than once -> dedup to one each, and
    # both active sources are represented.
    monkeypatch.setattr(chat_mod.db, "hybrid_search_chunks",
        lambda wsid, term, vec, source_ids=None, limit=None: [
            {"source_id": 1, "page_number": 1, "content": "c1"},
            {"source_id": 2, "page_number": 5, "content": "c2"},
        ])
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: [])
    out = await _retrieve_generic_context(_FakeProvider(), 99, [1, 2], "Worum geht es?")
    keys = [(c["source_id"], c["page_number"]) for c in out]
    assert keys.count((1, 1)) == 1      # deduped
    assert keys.count((2, 5)) == 1
    assert {c["source_id"] for c in out} == {1, 2}


@pytest.mark.asyncio
async def test_generic_retrieval_backfills_missing_source(monkeypatch):
    # The wide search only surfaces source 1; source 2 is backfilled by a
    # per-source mini-search ([2] in source_ids).
    def fake_search(wsid, term, vec, source_ids=None, limit=None):
        if source_ids == [2]:
            return [{"source_id": 2, "page_number": 9, "content": "per-source"}]
        return [{"source_id": 1, "page_number": 1, "content": "c1"}]
    monkeypatch.setattr(chat_mod.db, "hybrid_search_chunks", fake_search)
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: [])
    out = await _retrieve_generic_context(_FakeProvider(), 99, [1, 2], "q")
    assert {c["source_id"] for c in out} == {1, 2}


@pytest.mark.asyncio
async def test_generic_retrieval_raw_chunk_fallback_when_no_hits(monkeypatch):
    # Retrieval returns nothing (e.g. media with no matchable text) -> raw chunks.
    monkeypatch.setattr(chat_mod.db, "hybrid_search_chunks", lambda *a, **k: [])
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source",
        lambda sid: [{"source_id": sid, "page_number": 1, "content": "raw"}])
    out = await _retrieve_generic_context(_FakeProvider(), 99, [1], "q")
    assert out and out[0]["content"] == "raw"


# ── specific path: source-diversity reordering (pure part) ───────────────────

def test_diversify_keeps_first_hit_per_source_then_remainder():
    chunks = [
        {"source_id": 1, "page_number": 2},
        {"source_id": 1, "page_number": 3},
        {"source_id": 2, "page_number": 1},
    ]
    diverse, remaining, missing = _diversify_by_source(chunks, [1, 2, 3])
    # One representative per seen source first, rest deferred.
    assert diverse == [{"source_id": 1, "page_number": 2}, {"source_id": 2, "page_number": 1}]
    assert remaining == [{"source_id": 1, "page_number": 3}]
    # Source 3 produced no hit at all.
    assert missing == [3]


def test_diversify_reports_no_missing_when_all_present():
    chunks = [{"source_id": 1}, {"source_id": 2}]
    diverse, remaining, missing = _diversify_by_source(chunks, [1, 2])
    assert missing == []
    assert remaining == []
    assert diverse == chunks


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


# ── streaming usage extraction (include_usage final chunk) ───────────────────

class _Usage:
    def __init__(self, prompt_tokens, completion_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _Chunk:
    def __init__(self, usage=None):
        if usage is not None:
            self.usage = usage


def test_stream_usage_tokens_reads_final_usage_chunk():
    chunk = _Chunk(usage=_Usage(prompt_tokens=1234, completion_tokens=56))
    assert _stream_usage_tokens(chunk) == (1234, 56)


def test_stream_usage_tokens_none_when_no_usage_attr():
    # Normal content chunks carry no usage -> nothing to record.
    assert _stream_usage_tokens(_Chunk()) == (None, None)


def test_stream_usage_tokens_none_when_usage_is_none():
    # Provider that doesn't support include_usage sends usage=None.
    assert _stream_usage_tokens(_Chunk(usage=None)) == (None, None)


# ── langfuse trace enrichment for the streamed chat answer ───────────────────
#
# @observe finalizes the aia-chat trace when chat() returns its
# StreamingResponse; the real answer is produced LATER inside the streaming
# generator, outside the observe context. So enrichment must upsert the trace
# by id via the client, not via update_current_observation (which would target
# an already-closed context).

class _SpyClient:
    def __init__(self, raise_exc=False):
        self.traces = []
        self._raise = raise_exc

    def trace(self, **kwargs):
        self.traces.append(kwargs)
        if self._raise:
            raise RuntimeError("langfuse down")


class _SpyCtx:
    def __init__(self, client):
        self.client_instance = client


def test_enrich_chat_trace_upserts_trace_by_id(monkeypatch):
    client = _SpyClient()
    monkeypatch.setattr(chat_mod, "langfuse_context", _SpyCtx(client))
    _enrich_chat_trace("trace-abc", "Worum geht es?", "Es geht um X.", user_id="u-1", session_id="ws-9")
    assert client.traces == [{
        "id": "trace-abc",
        "input": "Worum geht es?",
        "output": "Es geht um X.",
        "user_id": "u-1",
        "session_id": "ws-9",
    }]


def test_enrich_chat_trace_noop_without_trace_id(monkeypatch):
    # No trace id captured (tracing disabled) -> nothing to update.
    client = _SpyClient()
    monkeypatch.setattr(chat_mod, "langfuse_context", _SpyCtx(client))
    _enrich_chat_trace(None, "q", "a", user_id="u", session_id="s")
    assert client.traces == []


def test_enrich_chat_trace_swallows_langfuse_errors(monkeypatch):
    # Tracing must never break the user-facing chat response.
    client = _SpyClient(raise_exc=True)
    monkeypatch.setattr(chat_mod, "langfuse_context", _SpyCtx(client))
    _enrich_chat_trace("t", "q", "a", user_id="u", session_id="s")  # must not raise


# ── SPECIFIC neighbor-chunk expansion: a fact beside a hit gets pulled in ────
# Regression for the "wer sind die autoren" miss AND the map-reduce hallucination:
# the answer chunk (a co-author name) embeds far from the question (vec_rank ~645)
# yet sits NEXT TO a retrieved anchor (the "Autoren" heading). Expanding each
# anchor's ±radius document window pulls the neighbour into ONE coherent single
# call — no whole-document read, no batch-splitting that invents names.

def _chunk(cid, page, text):
    return {"id": cid, "source_id": 1, "page_number": page, "content": text}


def test_expand_pulls_neighbours_of_an_anchor():
    # Anchor at index 2; the answer sits at index 4 and is NOT itself retrieved.
    doc = [{"id": 100 + i, "page_number": i, "content": f"c{i}"} for i in range(10)]
    anchors = [{"id": 102, "vec_distance": 0.4}]
    out = _expand_with_neighbors(anchors, doc, radius=3, source_id=1)
    ids = [c["id"] for c in out]
    assert ids == [100, 101, 102, 103, 104, 105]   # 102 ±3, clamped at 0
    assert 104 in ids                               # the deep neighbour is reached
    assert all(c["source_id"] == 1 for c in out)
    assert all(c["_anchor_dist"] == 0.4 for c in out)


def test_expand_merges_overlapping_windows_with_best_distance():
    doc = [{"id": 100 + i, "page_number": i, "content": f"c{i}"} for i in range(10)]
    anchors = [{"id": 102, "vec_distance": 0.6}, {"id": 104, "vec_distance": 0.3}]
    out = _expand_with_neighbors(anchors, doc, radius=1, source_id=7)
    ids = [c["id"] for c in out]
    assert ids == [101, 102, 103, 104, 105]         # union, deduped, document order
    # one merged span -> all carry the span's best (smallest) anchor distance
    assert all(c["_anchor_dist"] == 0.3 for c in out)


def test_expand_bridges_gap_between_nearby_anchors():
    # Two anchors 10 apart; the answer sits in the GAP between their ±3 windows.
    # Windows [100..103] and [107..113] leave 104,105,106 uncovered — bridging fills
    # them so a co-author named between two hits is not lost (the "authoren" case).
    doc = [{"id": 100 + i, "page_number": i, "content": f"c{i}"} for i in range(20)]
    anchors = [{"id": 100, "vec_distance": 0.5}, {"id": 110, "vec_distance": 0.7}]
    out = _expand_with_neighbors(anchors, doc, radius=3, source_id=1)
    ids = [c["id"] for c in out]
    assert ids == list(range(100, 114))             # contiguous span, gap bridged
    assert 105 in ids                               # the gap chunk is included


def test_pack_single_batch_is_one_window():
    # All chat paths now pack a single context window (no map-reduce). Overflow is
    # skipped rather than spilled into a second batch.
    chunks = [_chunk(i, i, f"FACT-{i:02d} " + "x" * 300) for i in range(1, 13)]
    batches, seen = _pack_context_batches(
        chunks, 1200, {1: 1}, {1: {"filename": "doc.pdf"}}, {}, multi=False,
    )
    assert len(batches) == 1
