"""Tests for the two RAG chat paths: GENERIC (overview, summary-based) and
SPECIFIC (topic-focused, hybrid search).

Covers the routing decision, the generic context assembly, the specific
source-diversity reordering, and the two async LLM helpers — all the logic that
decides WHICH context the tutor sees before it ever writes a citation.

LLM and DB are faked/monkeypatched so these are deterministic and offline.
"""
import pytest

from src.features.ai_assistant.routes import chat as chat_mod
from src.features.ai_assistant.routes.chat import (
    _should_skip_intent_classification,
    _sample,
    _assemble_generic_context,
    _diversify_by_source,
    _order_round_robin,
    _classify_intent,
    _rewrite_query,
    _split_doc_summary_by_markers,
    _stream_usage_tokens,
    _enrich_chat_trace,
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


# ── generic context assembly (db monkeypatched) ──────────────────────────────

def _patch_db(monkeypatch, *, sources, page_sums=None, chunks=None):
    page_sums = page_sums or {}
    chunks = chunks or {}
    monkeypatch.setattr(chat_mod.db, "get_aia_sources_by_workspace", lambda wsid: sources)
    monkeypatch.setattr(chat_mod.db, "get_page_summaries_by_source", lambda sid: page_sums.get(sid, []))
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: chunks.get(sid, []))


def test_generic_single_source_prefers_page_summaries(monkeypatch):
    _patch_db(
        monkeypatch,
        sources=[{"id": 1, "summary": "doc summary"}],
        page_sums={1: [{"page_number": 2, "summary": "S2"}, {"page_number": 5, "summary": "S5"}]},
    )
    out = _assemble_generic_context(99, [1])
    assert [c["page_number"] for c in out] == [2, 5]
    assert all(c["source_id"] == 1 for c in out)
    assert out[0]["content"] == "S2"


def test_generic_single_source_falls_back_to_doc_summary(monkeypatch):
    _patch_db(monkeypatch, sources=[{"id": 1, "summary": "the whole doc"}], page_sums={1: []})
    out = _assemble_generic_context(99, [1])
    assert len(out) == 1
    assert out[0]["content"] == "the whole doc"
    assert out[0]["page_number"] == 1


def test_generic_single_source_falls_back_to_full_chunks(monkeypatch):
    _patch_db(
        monkeypatch,
        sources=[{"id": 1, "summary": ""}],
        page_sums={1: []},
        chunks={1: [{"source_id": 1, "page_number": 3, "content": "raw"}]},
    )
    out = _assemble_generic_context(99, [1])
    assert out == [{"source_id": 1, "page_number": 3, "content": "raw"}]


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


def test_generic_multi_source_media_uses_raw_chunks(monkeypatch):
    media_chunks = [{"source_id": 2, "page_number": None, "start_time": float(i), "content": f"t{i}"} for i in range(20)]
    _patch_db(
        monkeypatch,
        sources=[{"id": 1, "summary": "d1"}, {"id": 2, "summary": "d2"}],
        page_sums={1: [{"page_number": 1, "summary": "S1"}], 2: []},
        chunks={2: media_chunks},
    )
    out = _assemble_generic_context(99, [1, 2])
    media = [c for c in out if c["source_id"] == 2]
    # No 8-cap anymore: all raw media chunks are candidates (start_time preserved).
    assert len(media) == 20
    assert all(c.get("start_time") is not None for c in media)
    assert [c["_seq"] for c in media] == list(range(20))


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
