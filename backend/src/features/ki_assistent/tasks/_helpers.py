"""Shared helpers for KI-Assistent Celery tasks."""

import concurrent.futures
import json
import os
import re

from langfuse.decorators import langfuse_context
from loguru import logger

from src import database as db
from src.limits import (
    TUTOR_SUMMARY_MAX_RETRIES,
    TUTOR_SUMMARY_TIMEOUT_SMALL,
    TUTOR_SUMMARY_TIMEOUT_LARGE,
    TUTOR_SUMMARY_MAX_TOKENS_SMALL,
    TUTOR_SUMMARY_MAX_TOKENS_LARGE,
    TUTOR_SUMMARY_MAX_TOKENS_BATCH,
    TUTOR_SUMMARY_CONTENT_MAX_CHARS,
    TUTOR_SUMMARY_PARALLEL_WORKERS_SMALL,
    TUTOR_SUMMARY_PARALLEL_WORKERS_LARGE,
    TUTOR_SUMMARY_BATCH_SIZE,
)
from src.tool_prompts import (
    TUTOR_SUMMARY_PAGE_SYSTEM as _SUMMARY_SYSTEM,
    TUTOR_SUMMARY_PAGE_USER_SMALL as _SUMMARY_USER_SMALL,
    TUTOR_SUMMARY_PAGE_USER_LARGE as _SUMMARY_USER_LARGE,
    TUTOR_SUMMARY_PAGE_BATCH_USER as _SUMMARY_BATCH_USER,
)

def _format_ts(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"

def _save_ki_tutor_output(username: str, module_uuid: str, filename: str, data: bytes) -> str:
    """Save a ki-tutor output file (e.g. presentation) in the structured folder."""
    from src.storage import USE_S3
    key = f"ki-tutor/{username}/{module_uuid}/outputs/{filename}"
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    from src.storage import STORAGE_ROOT
    dest = STORAGE_ROOT / "ki-tutor" / username / module_uuid / "outputs"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / filename).write_bytes(data)
    return str(dest / filename)

def _detect_language(text: str) -> str:
    """Simple heuristic language detection based on stop words."""
    german = {"der", "die", "das", "und", "ist", "ein", "eine", "mit", "von", "für", "auf", "des", "den", "auch", "nicht", "sich"}
    english = {"the", "is", "and", "of", "to", "in", "for", "that", "with", "this", "from", "are", "was", "not", "has"}
    words = text.lower().split()[:100]
    de = sum(1 for w in words if w in german)
    en = sum(1 for w in words if w in english)
    return "Deutsch" if de > en else "English"

def _parse_numbered_summaries(text: str, expected_count: int) -> list[str]:
    """Parse '1. summary\\n2. summary\\n...' format.

    Handles multi-line summaries by collecting all text between numbered prefixes.
    """
    # Split into numbered sections: "1. ...", "2. ...", etc.
    parts = re.split(r"(?m)^\s*\d+[\.)]\s*", text.strip())
    # First element is empty (text before first number) — drop it
    parts = [p.strip().replace("\n", " ") for p in parts if p.strip()]
    result = parts[:expected_count]
    while len(result) < expected_count:
        result.append("")
    return result[:expected_count]

def _clean_summary(text: str) -> str:
    """Strip <think> blocks and leading number prefix."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Unclosed <think> — model hit max_tokens while still reasoning
    if "<think>" in text:
        text = text[:text.index("<think>")].strip()
    text = re.sub(r"^\s*\d+[\.)]\s*", "", text).strip()
    return text

def _call_llm_with_retry(client, model, messages, temperature, max_tokens, timeout, extra_body):
    """Make an LLM call with retry on rate limits / timeouts."""
    import time as _time
    for attempt in range(TUTOR_SUMMARY_MAX_RETRIES):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                extra_body=extra_body or None,
            )
        except Exception as e:
            err_str = str(e)
            if ("429" in err_str or "timeout" in err_str.lower()) and attempt < TUTOR_SUMMARY_MAX_RETRIES - 1:
                wait = 30 * (attempt + 1)
                logger.warning(
                    "KI Tutor summaries: rate limit/timeout, retry in {}s ({}/{})",
                    wait, attempt + 1, TUTOR_SUMMARY_MAX_RETRIES,
                )
                _time.sleep(wait)
            else:
                raise

def _summarize_page(client, model, p, is_small, extra_body, lang):
    """Summarize a single page. Returns summary string."""
    sys_msg = _SUMMARY_SYSTEM.format(lang=lang)
    if is_small:
        user_msg = _SUMMARY_USER_SMALL.format(lang=lang, content=p["content"][:TUTOR_SUMMARY_CONTENT_MAX_CHARS])
    else:
        user_msg = _SUMMARY_USER_LARGE.format(lang=lang, content=p["content"][:TUTOR_SUMMARY_CONTENT_MAX_CHARS])

    timeout = TUTOR_SUMMARY_TIMEOUT_SMALL if is_small else TUTOR_SUMMARY_TIMEOUT_LARGE
    max_tokens = TUTOR_SUMMARY_MAX_TOKENS_SMALL if is_small else TUTOR_SUMMARY_MAX_TOKENS_LARGE

    resp = _call_llm_with_retry(
        client, model,
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
        temperature=0.1, max_tokens=max_tokens, timeout=timeout, extra_body=extra_body,
    )
    _msg = resp.choices[0].message
    summary = _clean_summary(_msg.content or getattr(_msg, "reasoning_content", None) or "")
    return summary

def _summarize_batch(client, model, pages_batch, lang):
    """Summarize a batch of pages in one request. Returns list[str] (one per page)."""
    n = len(pages_batch)
    sys_msg = _SUMMARY_SYSTEM.format(lang=lang)
    pages_text = "\n\n".join(
        f"---PAGE {i + 1}---\n{p['content'][:TUTOR_SUMMARY_CONTENT_MAX_CHARS]}"
        for i, p in enumerate(pages_batch)
    )
    user_msg = _SUMMARY_BATCH_USER.format(n=n, lang=lang, pages=pages_text)

    resp = _call_llm_with_retry(
        client, model,
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
        temperature=0.1, max_tokens=TUTOR_SUMMARY_MAX_TOKENS_BATCH,
        timeout=TUTOR_SUMMARY_TIMEOUT_LARGE, extra_body={},
    )
    _msg = resp.choices[0].message
    content = _msg.content or getattr(_msg, "reasoning_content", None) or ""
    # Strip <think> blocks (some models ignore think=False)
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    # Unclosed <think> — keep only what's before it
    if "<think>" in content:
        content = content[:content.index("<think>")].strip()
    summaries = _parse_numbered_summaries(content, n)
    return summaries

def _get_llm_client():
    """Return (client, model, provider) using the configured LLM provider."""
    from langfuse.openai import OpenAI
    from src.dependencies import _resolve_llm_provider
    _api_key, _base_url, _model, _provider = _resolve_llm_provider()
    client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=120)
    langfuse_context.update_current_observation(
        metadata={"provider": _provider, "base_url": _base_url, "model": _model},
    )
    return client, _model, _provider

def _clean_llm_json(text: str) -> str:
    """Strip markdown fences and leading/trailing whitespace from LLM JSON output."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


# ── Datentabelle generation ──────────────────────────────────────────────────

