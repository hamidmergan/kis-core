"""Builds a short summary per source, in batches and then merged."""
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

# Signs of a refusal due to overload, deliberately via the text.
_RATE_LIMIT_MARKERS = ("429", "rate limit", "rate_limit", "too many requests")


def _is_rate_limit(e: Exception) -> bool:
    if getattr(e, "status_code", None) == 429 or getattr(e, "code", None) == 429:
        return True
    msg = str(e).lower()
    return any(m in msg for m in _RATE_LIMIT_MARKERS)

# Ceiling of the output, short enough for many sources in one window.
_MAX_OUTPUT_TOKENS = 1280


def _batch_by_chars(chunks: list[dict], cap_chars: int) -> list[list[str]]:
    """Packs the chunks into batches below the character limit, in document order."""
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
    """One call with a simple retry, returns the trimmed text."""
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
        # Wait before the next attempt, growing and with jitter.
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
    """Builds a summary from the chunks of a source."""
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
