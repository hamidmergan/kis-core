"""Shared helpers for KI-Assistent Celery tasks."""

import concurrent.futures
import json
import os
import re

from langfuse.decorators import langfuse_context
from loguru import logger

from src import database as db
from src.limits import (
    AIA_SUMMARY_MAX_RETRIES,
    AIA_SUMMARY_TIMEOUT_SMALL,
    AIA_SUMMARY_TIMEOUT_LARGE,
    AIA_SUMMARY_MAX_TOKENS_SMALL,
    AIA_SUMMARY_MAX_TOKENS_LARGE,
    AIA_SUMMARY_MAX_TOKENS_BATCH,
    AIA_SUMMARY_CONTENT_MAX_CHARS,
    AIA_SUMMARY_PARALLEL_WORKERS_SMALL,
    AIA_SUMMARY_PARALLEL_WORKERS_LARGE,
    AIA_SUMMARY_BATCH_SIZE,
)
from src.tool_prompts import (
    aia_summary_page_system,
    AIA_SUMMARY_PAGE_USER_SMALL as _SUMMARY_USER_SMALL,
    AIA_SUMMARY_PAGE_USER_LARGE as _SUMMARY_USER_LARGE,
    AIA_SUMMARY_PAGE_BATCH_USER as _SUMMARY_BATCH_USER,
)

def _format_ts(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"

def _save_aia_output(user_id: int, workspace_uuid: str, filename: str, data: bytes) -> str:
    """Save an AIA output file (presentation, mindmap, etc.) under users/{user_id}/aia/."""
    from src.storage import USE_S3, aia_output_key
    key = aia_output_key(user_id, workspace_uuid, filename)
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    from src.storage import STORAGE_ROOT
    dest = STORAGE_ROOT / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)

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
    # First element is empty (text before first number) - drop it
    parts = [p.strip().replace("\n", " ") for p in parts if p.strip()]
    result = parts[:expected_count]
    while len(result) < expected_count:
        result.append("")
    return result[:expected_count]

def _clean_summary(text: str) -> str:
    """Strip <think> blocks and leading number prefix."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Unclosed <think> - model hit max_tokens while still reasoning
    if "<think>" in text:
        text = text[:text.index("<think>")].strip()
    text = re.sub(r"^\s*\d+[\.)]\s*", "", text).strip()
    return text

def _call_llm_with_retry(client, model, messages, temperature, max_tokens, timeout, extra_body):
    """Make an LLM call with one retry on timeout, immediate abort on rate limit."""
    import time as _time
    for attempt in range(2):
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
            if "429" in err_str:
                raise
            if "timeout" in err_str.lower() and attempt == 0:
                logger.warning("KI Tutor summaries: timeout, retrying once in 5s")
                _time.sleep(5)
            else:
                raise

def _summarize_page(client, model, p, is_small, extra_body, lang, locale: str = "de"):
    """Summarize a single page. Returns summary string.

    `lang` is the auto-detected source-text language ("Deutsch" / "English"),
    `locale` is the workspace owner's UI locale used to pick the meta-page
    sentinel ("Keine Zusammenfassung vorhanden" / "No summary available").
    """
    sys_msg = aia_summary_page_system(locale).format(lang=lang)
    if is_small:
        user_msg = _SUMMARY_USER_SMALL.format(lang=lang, content=p["content"][:AIA_SUMMARY_CONTENT_MAX_CHARS])
    else:
        user_msg = _SUMMARY_USER_LARGE.format(lang=lang, content=p["content"][:AIA_SUMMARY_CONTENT_MAX_CHARS])

    timeout = AIA_SUMMARY_TIMEOUT_SMALL if is_small else AIA_SUMMARY_TIMEOUT_LARGE
    max_tokens = AIA_SUMMARY_MAX_TOKENS_SMALL if is_small else AIA_SUMMARY_MAX_TOKENS_LARGE

    resp = _call_llm_with_retry(
        client, model,
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
        temperature=0.1, max_tokens=max_tokens, timeout=timeout, extra_body=extra_body,
    )
    _msg = resp.choices[0].message
    summary = _clean_summary(_msg.content or getattr(_msg, "reasoning_content", None) or "")
    return summary

def _summarize_batch(client, model, pages_batch, lang, locale: str = "de"):
    """Summarize a batch of pages in one request. Returns list[str] (one per page, ordered).

    See `_summarize_page` for the lang/locale split.
    """
    sys_msg = aia_summary_page_system(locale).format(lang=lang)
    pages_text = "\n\n".join(
        f"---PAGE {p['page_number']}---\n{p['content'][:AIA_SUMMARY_CONTENT_MAX_CHARS]}"
        for p in pages_batch
    )
    user_msg = _SUMMARY_BATCH_USER.format(n=len(pages_batch), lang=lang, pages=pages_text)

    resp = _call_llm_with_retry(
        client, model,
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
        temperature=0.1, max_tokens=AIA_SUMMARY_MAX_TOKENS_BATCH,
        timeout=AIA_SUMMARY_TIMEOUT_LARGE, extra_body={},
    )
    _msg = resp.choices[0].message
    content = _msg.content or getattr(_msg, "reasoning_content", None) or ""
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if "<think>" in content:
        content = content[:content.index("<think>")].strip()

    # Parse JSON response: {"5": "summary", "6": "summary"}
    parsed = None
    # Try direct JSON parse
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        pass
    # Try fixing single quotes -> double quotes
    if parsed is None:
        try:
            parsed = json.loads(content.replace("'", '"'))
        except (json.JSONDecodeError, ValueError):
            pass
    # Try extracting JSON block from response
    if parsed is None:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
            except (json.JSONDecodeError, ValueError):
                try:
                    parsed = json.loads(match.group().replace("'", '"'))
                except (json.JSONDecodeError, ValueError):
                    pass
    # Fallback to numbered list parsing
    if parsed is None:
        logger.warning("KI Tutor: batch summary returned invalid JSON, falling back to numbered parse")
        return _parse_numbered_summaries(content, len(pages_batch))

    # Map back to ordered list by page_number
    result = []
    for p in pages_batch:
        key = str(p["page_number"])
        summary = parsed.get(key, "")
        result.append(_clean_summary(summary) if summary else "")
    return result

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

# Doc-summary input budget: large enough for a 100-min transcript (~50k chars)
# or ~75 page-summaries; small enough to fit a 32k-token context with output budget.
_DOC_SUMMARY_INPUT_MAX_CHARS = 80_000
_DOC_SUMMARY_MAX_TOKENS = 600  # ~300-word English overview


def _gather_doc_summary_input(source_id: int) -> str:
    """Pick the best compact input for a doc-level summary of this source.

    Prefer page-summaries (already compressed) when present; otherwise fall back
    to the raw chunks. Each block is prefixed with a position marker - ``[p.X]``
    for PDF pages, ``[t:SECS]`` for media timestamps - so the LLM can carry the
    markers through into the doc-summary output (used for clickable citations).
    Output is truncated to _DOC_SUMMARY_INPUT_MAX_CHARS so the downstream LLM
    call stays within typical context windows.
    """
    page_summaries = db.get_page_summaries_by_source(source_id)
    if page_summaries:
        joined = "\n".join(
            f"[p.{s['page_number']}] {s['summary']}" for s in page_summaries if s.get("summary")
        )
    else:
        chunks = db.get_aia_chunks_by_source(source_id)
        parts: list[str] = []
        for c in chunks:
            content = (c.get("content") or "").strip()
            if not content:
                continue
            start_time = c.get("start_time")
            if start_time is not None:
                marker = f"[t:{int(start_time)}]"
            elif c.get("page_number"):
                marker = f"[p.{c['page_number']}]"
            else:
                marker = ""
            parts.append(f"{marker} {content}" if marker else content)
        joined = "\n".join(parts)
    return joined[:_DOC_SUMMARY_INPUT_MAX_CHARS]


def generate_doc_summary(source_uuid: str) -> str | None:
    """Generate and persist an English doc-level summary for a source.

    Returns the saved summary on success, ``None`` if the source has no usable
    content (e.g. indexing failed before chunks were stored).
    """
    from src.tool_prompts import AIA_DOC_SUMMARY_SYSTEM, AIA_DOC_SUMMARY_USER

    source = db.get_aia_source(source_uuid)
    if source is None:
        logger.warning("KI Tutor doc-summary: source {} not found, skipping", source_uuid)
        return None

    content = _gather_doc_summary_input(source["id"])
    if not content.strip():
        logger.warning("KI Tutor doc-summary: no content available for {}", source_uuid)
        return None

    client, model, _provider = _get_llm_client()
    resp = _call_llm_with_retry(
        client, model,
        [
            {"role": "system", "content": AIA_DOC_SUMMARY_SYSTEM},
            {"role": "user", "content": AIA_DOC_SUMMARY_USER.format(content=content)},
        ],
        temperature=0.2,
        max_tokens=_DOC_SUMMARY_MAX_TOKENS,
        timeout=AIA_SUMMARY_TIMEOUT_LARGE,
        extra_body={},
    )
    msg = resp.choices[0].message
    raw = msg.content or getattr(msg, "reasoning_content", None) or ""
    summary = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    if not summary:
        logger.warning("KI Tutor doc-summary: empty LLM output for {}", source_uuid)
        return None

    db.update_aia_source_summary(source_uuid, summary)
    logger.info("KI Tutor doc-summary: saved {} chars for {}", len(summary), source_uuid)
    return summary


def _clean_llm_json(text: str) -> str:
    """Strip markdown fences and leading/trailing whitespace from LLM JSON output."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


# ── DataTable generation ──────────────────────────────────────────────────

