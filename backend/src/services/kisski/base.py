"""Basis-Klasse der KISSKI-Client-Mixins + interne Helper."""

import json

from langfuse.openai import OpenAI


def is_transient_error(e: Exception) -> bool:
    """Match transient upstream failures worth retrying (5xx, timeouts, connection errors)."""
    status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
    if isinstance(status, int) and 500 <= status < 600:
        return True
    msg = str(e).lower()
    return any(kw in msg for kw in (
        "internal server error", "bad gateway", "service unavailable",
        "gateway timeout", "timeout", "connection", "temporarily",
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


class _KisskiBase:
    """Gemeinsame Attribute aller KISSKI-Client-Mixins.

    Mixins (`_ScriptsMixin`, `_SummaryMixin`, `_WhisperMixin`, `_WhisperChunkedMixin`)
    erwarten diese Instanz-Variablen. Die konkrete Client-Klasse setzt sie hier."""

    def __init__(self, api_key: str, base_url: str, model: str, provider: str = "kisski"):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._provider = provider
        self._base_url = base_url
        self._extra_body: dict = {}
        # Batch-Settings (werden in _ScriptsMixin.generate_scripts_batch verwendet).
        # Defaults sind provider-unabhängig gleich; Platzhalter für künftige Provider-Profile.
        if provider == "ollama":
            self._batch_max_workers: int = 3
            self._batch_timeout: float = 180.0
            self._batch_size: int = 3
        else:
            self._batch_max_workers = 3
            self._batch_timeout = 180.0
            self._batch_size = 3
