"""Base class of the OpenAI-compat LLM client mixins + internal helpers."""

import json

import httpx
from langfuse.openai import AsyncOpenAI, OpenAI

# Connect + headers + first-byte deadline. Once the upstream starts streaming, the
# per-chunk inactivity timeout (in chat.py) takes over. Default OpenAI SDK timeout
# is 600s — far too generous for an interactive chat where requests pile up if the
# provider stalls.
_LLM_HTTP_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


def is_transient_error(e: Exception) -> bool:
    """Match transient upstream failures worth retrying (5xx, 429 rate-limit, timeouts, connection errors)."""
    status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
    if isinstance(status, int) and (500 <= status < 600 or status == 429):
        return True
    msg = str(e).lower()
    return any(kw in msg for kw in (
        "internal server error", "bad gateway", "service unavailable",
        "gateway timeout", "timeout", "connection", "temporarily",
        "rate limit", "429",
    ))


def load_prompt(key: str, default: str) -> str:
    """Load a system prompt from DB settings, falling back to the hardcoded default."""
    try:
        from src import database as db
        val = db.get_setting(key, "")
        return val if val.strip() else default
    except Exception:
        return default


def clean_whisper_response(raw: str) -> str:
    """Clean Whisper API response that may be JSON-encoded (wrapped in quotes with escaped newlines)."""
    text = raw.strip()
    if text.startswith('"') and text.endswith('"'):
        try:
            text = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            text = text[1:-1]
            text = text.replace("\\n", "\n").replace("\\r", "\r")
    return text.strip()


class _OpenAICompatBase:
    """Shared attributes of all OpenAI-compat LLM client mixins.

    Mixins (`_ScriptsMixin`, `_SummaryMixin`, `_WhisperMixin`, `_WhisperChunkedMixin`)
    expect these instance variables. The concrete client class sets them here.
    The ``provider`` field is a free-form tag for telemetry / logging only and
    has no effect on request shape (the API surface is the same OpenAI spec)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        provider: str = "kisski",
        whisper_model: str = "whisper-large-v2",
    ):
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=_LLM_HTTP_TIMEOUT)
        # Async twin for streaming endpoints that need cancel-on-disconnect.
        self._async_client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=_LLM_HTTP_TIMEOUT)
        self._model = model
        self._provider = provider
        self._base_url = base_url
        self._whisper_model = whisper_model
        self._extra_body: dict = {}
        # Batch settings (used in _ScriptsMixin.generate_scripts_batch).
        # Defaults are provider-independent; placeholders for future provider profiles.
        self._batch_max_workers: int = 3
        self._batch_timeout: float = 180.0
        self._batch_size: int = 3
