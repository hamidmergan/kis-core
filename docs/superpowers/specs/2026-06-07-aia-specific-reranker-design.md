# AIA SPECIFIC Reranker — Design Spec

**Date:** 2026-06-07
**Status:** **DEFERRED (2026-06-07)** — design is sound, implementation NOT pursued. Blocked by infra (see Prerequisite): SAIA/KISSKI has no `/rerank`, no local GPU, external APIs conflict with the privacy posture. And the existing never-truncate map-reduce already returns correct answers, so a reranker would be mostly a cost/latency optimization. Revisit if SAIA exposes a reranker, a GPU becomes available, or an EU-compliant rerank API is acceptable.
**Scope:** Add an optional cross-encoder reranker to the SPECIFIC retrieval path.

---

## Problem

SPECIFIC retrieval pulls ~200 hybrid hits per source ([chunks.py `hybrid_search_chunks`](../../../backend/src/features/ai_assistant/repository/chunks.py)), fused by RRF (vector top-80 + BM25 top-80). RRF ordering is **coarse**: query and chunk are embedded separately, so a chunk that answers the question can sit deep in the ranking (the observed case: an author name at fused rank ~59).

The current system compensates with **never-truncate map-reduce**: when the budget-selected content exceeds one context window it spills into additional batches, each answered by its own LLM call, then merged. That is a *brute-force workaround* for imprecise ranking — it shows the model more, instead of ranking better. Costs scale inversely with the admin context budget (small budget → many batches → many LLM calls).

A **cross-encoder reranker** scores `(query, chunk)` *jointly*, so the answer-bearing chunk rises to the top (rank ~59 → ~3). Then the budget-selected content fits one window and map-reduce rarely (or never) fires — simpler **and** more accurate.

## Goal

Insert an **optional, graceful** reranker between per-source hybrid search and the distance gate in the SPECIFIC path. Reranker **only reorders**; the existing distance gate, relevance-weighted budget split, and never-truncate map-reduce stay unchanged (map-reduce remains the safety net, fires less often).

## Non-Goals

- **GENERIC stays untouched.** Reranking would narrow overview breadth, violating the established "Überblick-Breite nie verkleinern" principle.
- Not solving the gate-drop-before-rerank edge in v1 (see Known Boundaries) — but `rerank_score` is retained on chunks so the fix is a small later change.
- No in-process model, no new heavy backend dependency (no torch). Reranker is an external OpenAI/Cohere-style endpoint, consistent with "Ollama extern" / lean self-hosting.

## Decisions (v1)

- **Gate signal stays `vec_distance` (reorder-only).** Switching the source gate to `rerank_score` would remove the gate-drop boundary, but a rerank-score threshold cannot be tuned blind — it needs real query data that only exists once the reranker runs. So: ship the low-risk reorder-only core, measure, then decide the gate upgrade with data. `rerank_score` is attached to chunks even in v1, making that upgrade a small, data-informed change rather than a rewrite.
- **Rerank the full per-source retrieved set (≤ `_SPECIFIC_RETRIEVE_LIMIT` = 200), no extra candidate cap.** The motivating case is an answer chunk at fused rank ~59; an aggressive candidate cap (e.g. top-50) would drop it *before* the reranker sees it — reintroducing the exact truncation bug. 200 short pairs are cheap on a served cross-encoder. The single bound is the existing retrieve limit. **Cloud caveat:** providers like Cohere bill per ~100 documents per request, so cloud-rerank cost scales with the retrieved set; self-hosted (Infinity/TEI) does not. Documented, not capped.

## Prerequisite (BLOCKER — resolve before any code)

A reachable Cohere-compatible `/rerank` endpoint must exist for the target deployment. **Finding (2026-06-07):** the primary cloud provider **SAIA/GWDG (KISSKI) offers NO rerank endpoint** — documented endpoints are `/chat/completions`, `/completions`, `/embeddings`, `/models`, `/documents`, images, audio; embeddings exist (`e5-mistral-7b-instruct`, `multilingual-e5-large-instruct`, `qwen3-embedding-4b`) but no reranker. ([SAIA docs](https://docs.hpc.gwdg.de/services/ai-services/saia/index.html))

So there is **no zero-effort cloud path**. The three options, each with a real cost:

1. **Self-host Infinity / HuggingFace TEI** serving `bge-reranker-v2-m3` — the only self-hosted path; adds a new service (GPU/CPU, ops, monitoring) to the stack. Not "trivially local."
2. **Commercial API (Cohere/Jina)** — data leaves the academic/EU boundary, conflicting with KISSKI's sensitive/critical-infrastructure privacy posture. Likely a non-starter for that reason.
3. **Defer** — keep the existing never-truncate map-reduce as the substitute (it works) until SAIA exposes a reranker.

This decision gates whether the implementation plan is written at all. Once a path is chosen, a one-off `curl` validates the request/response shape assumed in Component 1.

---

## Architecture

### Component 1 — Rerank provider abstraction

New file `backend/src/services/aia_rerank.py`, mirroring `aia_embeddings.py`:

```python
class RerankProvider(ABC):
    @abstractmethod
    def rerank(self, query: str, documents: list[str],
               top_n: int | None = None) -> list[tuple[int, float]]:
        """Return (original_index, relevance_score) pairs, sorted score-desc."""

class CohereCompatRerankProvider(RerankProvider):
    """POST {base_url}/rerank with {model, query, documents, top_n}.
    Parses {"results": [{"index": i, "relevance_score": s}, ...]}.
    Standard shape for Cohere, Jina, HuggingFace TEI, Infinity."""
    def __init__(self, base_url: str, api_key: str, model: str): ...

def get_rerank_provider() -> RerankProvider | None:
    """Resolve the 'rerank' feature route. Returns None when unconfigured —
    rerank is OPTIONAL (unlike embedding, which raises). Any resolution error
    → None, so retrieval always works without a reranker."""
```

- The `/rerank` request/response shape is the Cohere convention, which Jina, TEI, and Infinity all implement. One client class covers self-hosted (Infinity/TEI serving `bge-reranker-v2-m3`) and cloud (Cohere/Jina) by base_url/key/model alone.
- `bge-reranker-v2-m3` is multilingual (100+ languages) → satisfies language-agnostic requirement across tiers (the reranker is a small ~560M model, independent of the chat-LLM tier).

### Component 2 — `rerank` feature route

- `feature_router.resolve()` is already dynamic (`db.get_route(feature)` takes any string — verified), so no enum/registry blocks a new feature key.
- Like `aia_embeddings.get_embedding_provider`, `get_rerank_provider` resolves the binding and builds the client directly (does **not** go through `make_llm_client`, since `/rerank` is not the chat/embeddings shape).
- Admin-UI work: surface `"rerank"` in the configurable-feature list so an admin can assign a provider+model. (Exact frontend/backend files to be pinned in the implementation plan.)

### Component 3 — Wire into SPECIFIC retrieval

In `chat.py` (~[1080-1110](../../../backend/src/features/ai_assistant/routes/chat.py)), between per-source `hybrid_search_chunks` and the distance gate:

1. `provider = get_rerank_provider()`. If `None` → skip entirely (behaviour identical to today).
2. If present: for each source's `hits`, call `provider.rerank(query, [c["content"] for c in hits])`, reorder `hits` by the returned index order, attach `c["rerank_score"]`.
3. Run all sources **concurrently** via `asyncio.gather` of `asyncio.to_thread(provider.rerank, ...)` — also removes the current serial per-source query latency for this step.
4. Distance gate + `_allocate_specific_budget` + `_take_chunks_within` **unchanged**. Because hits are now in rerank order, `_take_chunks_within` (takes the prefix) keeps the rerank-best chunks → the deep answer chunk lands in budget.

### Data flow

```
query
  → per-source hybrid search (200/src)        [unchanged]
  → [NEW] rerank each source's hits, reorder   [optional, parallel, graceful]
  → source-level distance gate                 [unchanged, on vec_distance]
  → relevance-weighted budget split            [unchanged]
  → pack into batches (usually 1)              [unchanged]
  → LLM (map-reduce only if still >1 batch)    [unchanged, fires less often]
```

---

## Error Handling (all graceful)

- **No `rerank` route configured** → `get_rerank_provider()` returns `None` → reranking skipped, exact current behaviour.
- **Rerank call fails / times out** (~20s timeout) → catch, keep the original RRF order for that source, log a warning. Never breaks the answer.
- **Partial failure** (one source's rerank fails in the gather) → that source keeps RRF order; others use reranked order.
- **Malformed response** (missing `results`/`index`) → treated as failure → original order.

## Testing (TDD)

1. `CohereCompatRerankProvider.rerank` parses a mocked `/rerank` response into correctly-ordered `(index, score)` pairs.
2. `get_rerank_provider()` returns `None` when the route is unconfigured / resolution raises.
3. Reorder helper: given hits + a rerank result, hits return in rerank order with `rerank_score` attached; given an empty/failed rerank, original order is preserved unchanged.
4. Scenario test: a chunk with poor RRF rank but top rerank score ends up inside the budget-selected set (the rank-59 case).

## Known Boundaries (documented, not solved here)

- **Gate-drop before rerank:** a source whose *closest* chunk is off-topic by cosine can be dropped by the multi-source distance gate *before* the reranker sees it — even if a deeper chunk in that source holds the answer. Reranking within-source cannot rescue a source the gate already removed. This is the same bug class the reranker targets, at the source level. Deliberately deferred (see Decisions): `rerank_score` is attached in v1, so the later fix is "gate on best `rerank_score` instead of `vec_distance`" once a threshold can be tuned against real queries.
- **Latency:** adds one rerank round-trip (parallel across sources, ~100-300 ms on a served cross-encoder). Net latency typically improves when map-reduce previously fired (fewer LLM calls); for already-single-batch queries it adds a small fixed cost.

## Config & Docs

- Admin UI: new `rerank` feature, assignable to any OpenAI/Cohere-compatible provider. API keys stay encrypted in the DB (provider-config approach), not `.env`.
- README: document running Infinity or HuggingFace TEI with `bge-reranker-v2-m3` as the self-hosted `/rerank` endpoint (same precedent as the TTS-provider setup docs).

## Files

**New:**
- `backend/src/services/aia_rerank.py` — provider abstraction + `get_rerank_provider`
- `backend/tests/test_rerank.py` — provider parsing, None path, reorder helper, scenario

**Modified:**
- `backend/src/features/ai_assistant/routes/chat.py` — rerank step in SPECIFIC retrieval (parallel, graceful)
- Admin feature list (frontend + backend) — expose `"rerank"` (exact files in the plan)
- `README` — self-hosted reranker setup
```
