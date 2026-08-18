"""Per-source DOC SUMMARY builder (ingest-side, offline).

Builds ONE compact summary per source from its chunks, used to represent the
source in GENERIC/overview answers (and optionally as a thin base layer in
SPECIFIC). Chunk-based → works for PDF pages and media transcripts alike.

Strategy (map-reduce, fill-to-cap):
- Pack chunks into batches whose combined size stays under ``cap_chars`` so each
  LLM call's prefill finishes well under the myLab time-to-first-token limit (a
  whole large doc in one call would time out — see private/rag-log.md).
- MAP: summarize each batch (1 call).
- REDUCE: if >1 batch, merge the partial summaries into one (1 combine call).
- One batch → return its summary directly (no combine).

Pure of DB/Celery: callers pass an LLM client + model + cap; this module only
builds text. Raises on persistent LLM failure so the ingest task can mark the
source 'failed' (→ user retry).
"""
from __future__ import annotations

import random
import time
from typing import Any, Optional

from loguru import logger

from src.features.ai_assistant.prompts.summarizer_prompts import (
    aia_summary_system,
    aia_summary_user,
    aia_summary_combine_system,
    aia_summary_combine_user,
)

# Markers for a throttling rejection. String-based on purpose — providers raise
# heterogeneous types.
_RATE_LIMIT_MARKERS = ("429", "rate limit", "rate_limit", "too many requests")


def _is_rate_limit(e: Exception) -> bool:
    if getattr(e, "status_code", None) == 429 or getattr(e, "code", None) == 429:
        return True
    msg = str(e).lower()
    return any(m in msg for m in _RATE_LIMIT_MARKERS)

# Ceiling on summary output: compact enough that many summaries coexist in one
# GENERIC window (~5k chars/source max), but high enough to cover EVERY section
# (the prompt enforces brevity per bullet, so small docs stay well under it).
# ~1280 tok ≈ ~4.5k chars. Input is bounded by ``cap_chars`` per call.
_MAX_OUTPUT_TOKENS = 1280


def _batch_by_chars(chunks: list[dict], cap_chars: int) -> list[list[str]]:
    """Pack chunk contents into batches, each ≤ cap_chars (fill-to-cap, doc order).

    A single chunk larger than the cap still gets its own batch (never dropped).
    """
    batches: list[list[str]] = []
    cur: list[str] = []
    used = 0
    for c in chunks:
        content = (c.get("content") or "").strip()
        if not content:
            continue
        if cur and used + len(content) > cap_chars:
            batches.append(cur)
            cur, used = [], 0
        cur.append(content)
        used += len(content)
    if cur:
        batches.append(cur)
    return batches


def _call(
    client: Any, model: str, system: str, user: str, *, retries: int,
    temperature: float = 0.4,
) -> str:
    """One chat-completion call with simple retry; returns stripped text.

    ``temperature`` is lower for the combine/reduce step: merging partials is a
    faithfulness task (don't invent section-number attributions), so we sample
    more conservatively there than in the map step.
    """
    last: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                frequency_penalty=0.5,  # discourage degenerate repetition loops
                max_tokens=_MAX_OUTPUT_TOKENS,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
            last = RuntimeError("empty summary response")
        except Exception as e:  # retried below, re-raised if all attempts fail
            last = e
            rate_limited = _is_rate_limit(e)
            logger.warning(
                "Summary call failed (attempt {}/{}, rate_limit={}): {}",
                attempt + 1, retries + 1, rate_limited, e,
            )
        # Back off before the next attempt (no sleep after the final one). A
        # throttled call needs a real wait; other errors get a short pause.
        # Exponential + jitter so concurrent ingests don't resync.
        if attempt < retries:
            base = 8.0 if (last is not None and _is_rate_limit(last)) else 2.0
            delay = min(base * (2 ** attempt), 60.0) + random.uniform(0, 1.0)
            time.sleep(delay)
    raise last if last else RuntimeError("summary call failed")


def build_source_summary(
    chunks: list[dict],
    client: Any,
    model: str,
    cap_chars: int,
    *,
    retries: int = 2,
) -> str:
    """Build ONE doc summary from a source's chunks.

    fill-to-cap batches → MAP (1 call/batch) → REDUCE (combine, only if >1 batch).
    Raises on persistent LLM failure so the caller can mark the source 'failed'.
    Returns "" for an empty/contentless source.
    """
    batches = _batch_by_chars(chunks, cap_chars)
    if not batches:
        return ""

    partials: list[str] = []
    for i, batch in enumerate(batches, 1):
        text = "\n\n".join(batch)
        partial = _call(
            client, model, aia_summary_system(), aia_summary_user(text), retries=retries
        )
        partials.append(partial)
        logger.info(
            "Summary map {}/{}: {} chars in → {} chars out",
            i, len(batches), len(text), len(partial),
        )

    if len(partials) == 1:
        return partials[0]

    combined = _call(
        client, model,
        aia_summary_combine_system(),
        aia_summary_combine_user(partials),
        retries=retries,
        temperature=0.2,  # faithful merge: don't invent section-number attributions
    )
    logger.info("Summary combine: {} partials → {} chars", len(partials), len(combined))
    return combined
