"""Retries a disrupted model call, but never a refusal due to overload."""

import time

from loguru import logger


# Three attempts, after that the failure stands.
ATTEMPTS = 3

# Pause before the second and third attempt.
BACKOFF_SECONDS = (2, 6)


def is_retryable(exc: Exception) -> bool:
    """Whether a second attempt has any chance at all."""
    status = getattr(exc, "status_code", None)
    if status is not None:
        # 429 is the real reason for the distinction here, see the module header.
        return status >= 500
    try:
        import openai
    except ImportError:  # pragma: no cover - openai gehört zu den Abhängigkeiten
        return False
    return isinstance(exc, openai.APIConnectionError)


def call_with_retry(func, *args, sleep_fn=time.sleep, **kwargs):
    """Calls func and retries on a disruption, the last error propagates."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == ATTEMPTS or not is_retryable(e):
                raise
            wait = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS)) - 1]
            logger.warning(
                "KI Tutor: Modell-Aufruf gestört ({}), Versuch {} von {} in {} s: {}",
                type(e).__name__, attempt + 1, ATTEMPTS, wait, e,
            )
            sleep_fn(wait)


class _Completions:
    """Only ``create`` is intercepted, everything else passes through."""

    def __init__(self, inner, sleep_fn):
        self._inner = inner
        self._sleep_fn = sleep_fn

    def create(self, *args, **kwargs):
        return call_with_retry(self._inner.create, *args, sleep_fn=self._sleep_fn, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _Chat:
    def __init__(self, inner, sleep_fn):
        self._inner = inner
        self.completions = _Completions(inner.completions, sleep_fn)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class RetryingClient:
    """A wrapper around the client, only the model call is retried."""

    def __init__(self, inner, sleep_fn=time.sleep):
        self._inner = inner
        self.chat = _Chat(inner.chat, sleep_fn)

    def __getattr__(self, name):
        return getattr(self._inner, name)
