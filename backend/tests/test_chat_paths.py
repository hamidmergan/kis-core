"""Tests for the two RAG chat paths: GENERIC (overview, multi-query retrieval)
and SPECIFIC (topic-focused, hybrid search). Both are pgvector-only — no
summaries are precomputed at upload.

Covers the routing decision, the generic search-strategy decomposition +
multi-query retrieval, the specific source-diversity reordering, and the async
LLM helpers — all the logic that decides WHICH context the tutor sees before it
ever writes a citation.

LLM and DB are faked/monkeypatched so these are deterministic and offline.
"""
import pytest

from src.features.ai_assistant.routes import chat as chat_mod
from src.features.ai_assistant.routes.chat import (
    _should_skip_intent_classification,
    _sample,
    _generate_search_strategy,
    _retrieve_generic_context,
    _diversify_by_source,
    _order_round_robin,
    _classify_intent,
    _rewrite_query,
    _stream_usage_tokens,
    _enrich_chat_trace,
    _INTENT_MAX_WORDS,
    _GENERIC_MAX_QUERIES,
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


# ── query rewrite (condense follow-up) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_rewrite_query_returns_rewritten():
    hist = [{"role": "user", "content": "Wer leitet das Seminar?"}]
    out = await _rewrite_query(FakeLLM(content="Wer leitet das wissenschaftliche Seminar?"), hist, "Und wer noch?")
    assert out == "Wer leitet das wissenschaftliche Seminar?"


@pytest.mark.asyncio
async def test_rewrite_query_keeps_original_on_error():
    out = await _rewrite_query(FakeLLM(raise_exc=True), [], "Original?")
    assert out == "Original?"


@pytest.mark.asyncio
async def test_rewrite_query_rejects_overlong_output():
    out = await _rewrite_query(FakeLLM(content="x" * 1001), [], "Original?")
    assert out == "Original?"


# ── _sample: even-spaced cap used in multi-source generic ────────────────────

def test_sample_returns_all_when_under_cap():
    assert _sample([1, 2, 3], 5) == [1, 2, 3]


def test_sample_caps_and_spreads_evenly():
    out = _sample(list(range(100)), 4)
    assert len(out) == 4
    assert out[0] == 0          # always includes the start
    assert out == sorted(out)   # preserves order
    assert len(set(out)) == 4   # no duplicates


# ── generic path: search-strategy decomposition (provider faked) ─────────────

@pytest.mark.asyncio
async def test_search_strategy_parses_lines_and_anchors_question():
    # The LLM proposes facets; the original question is always kept as anchor[0].
    llm = FakeLLM(content="Hauptthemen\nKernkonzepte\n- Struktur")
    terms = await _generate_search_strategy(llm, "Worum geht es?")
    assert terms[0] == "Worum geht es?"
    assert "Hauptthemen" in terms
    assert "Struktur" in terms          # leading "- " stripped
    assert len(terms) <= _GENERIC_MAX_QUERIES


@pytest.mark.asyncio
async def test_search_strategy_falls_back_to_question_on_error():
    terms = await _generate_search_strategy(FakeLLM(raise_exc=True), "Worum geht es?")
    assert terms == ["Worum geht es?"]


# ── generic path: multi-query pgvector retrieval (db/provider monkeypatched) ──

class _FakeProvider:
    def embed_one(self, text):
        return [0.0, 0.0]


@pytest.mark.asyncio
async def test_generic_retrieval_merges_dedups_and_diversifies(monkeypatch):
    # Two sub-queries each return the same two chunks -> dedup to one each, and
    # both active sources are represented.
    llm = FakeLLM(content="thema a\nthema b")
    monkeypatch.setattr(chat_mod.db, "hybrid_search_chunks",
        lambda wsid, term, vec, source_ids=None, limit=None: [
            {"source_id": 1, "page_number": 1, "content": "c1"},
            {"source_id": 2, "page_number": 5, "content": "c2"},
        ])
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: [])
    out = await _retrieve_generic_context(llm, _FakeProvider(), 99, [1, 2], "Worum geht es?")
    keys = [(c["source_id"], c["page_number"]) for c in out]
    assert keys.count((1, 1)) == 1      # deduped despite multiple queries
    assert keys.count((2, 5)) == 1
    assert {c["source_id"] for c in out} == {1, 2}


@pytest.mark.asyncio
async def test_generic_retrieval_backfills_missing_source(monkeypatch):
    # Global search only ever surfaces source 1; source 2 is backfilled by a
    # per-source mini-search ([2] in source_ids).
    llm = FakeLLM(content="q1")
    def fake_search(wsid, term, vec, source_ids=None, limit=None):
        if source_ids == [2]:
            return [{"source_id": 2, "page_number": 9, "content": "per-source"}]
        return [{"source_id": 1, "page_number": 1, "content": "c1"}]
    monkeypatch.setattr(chat_mod.db, "hybrid_search_chunks", fake_search)
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: [])
    out = await _retrieve_generic_context(llm, _FakeProvider(), 99, [1, 2], "q")
    assert {c["source_id"] for c in out} == {1, 2}


@pytest.mark.asyncio
async def test_generic_retrieval_raw_chunk_fallback_when_no_hits(monkeypatch):
    # Retrieval returns nothing (e.g. media with no matchable text) -> raw chunks.
    llm = FakeLLM(content="q1")
    monkeypatch.setattr(chat_mod.db, "hybrid_search_chunks", lambda *a, **k: [])
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source",
        lambda sid: [{"source_id": sid, "page_number": 1, "content": "raw"}])
    out = await _retrieve_generic_context(llm, _FakeProvider(), 99, [1], "q")
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
