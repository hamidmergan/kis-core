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
    if isinstance(exc, openai.APITimeoutError) and not _never_arrived(exc):
        # The provider worked the whole time limit, a second attempt costs the same again.
        return False
    return isinstance(exc, openai.APIConnectionError)


def _never_arrived(exc: BaseException) -> bool:
    """Whether a timeout struck before the request reached the provider."""
    import httpx
    seen = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, (httpx.ConnectTimeout, httpx.PoolTimeout)):
            return True
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return False


def _soft_deadline(exc: BaseException):
    """Celery's soft deadline, also when the SDK hid it behind a connection error."""
    try:
        from celery.exceptions import SoftTimeLimitExceeded
    except ImportError:  # pragma: no cover - celery is a dependency
        return None
    seen = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, SoftTimeLimitExceeded):
            return exc
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return None


def call_with_retry(func, *args, sleep_fn=time.sleep, **kwargs):
    """Calls func and retries on a disruption, the last error propagates."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            deadline = _soft_deadline(e)
            if deadline is not None:
                # Another attempt would run into the hard kill, the task needs the deadline to requeue in time.
                raise deadline
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

    def __init__(self, inner, sleep_fn, extra_body=None):
        self._inner = inner
        self._sleep_fn = sleep_fn
        self._extra_body = dict(extra_body or {})

    def create(self, *args, **kwargs):
        if self._extra_body:
            # What a single call sends itself wins over the default.
            kwargs["extra_body"] = {**self._extra_body, **(kwargs.get("extra_body") or {})}
        return call_with_retry(self._inner.create, *args, sleep_fn=self._sleep_fn, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _Chat:
    def __init__(self, inner, sleep_fn, extra_body=None):
        self._inner = inner
        self.completions = _Completions(inner.completions, sleep_fn, extra_body)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class RetryingClient:
    """A wrapper around the client, only the model call is retried."""

    def __init__(self, inner, sleep_fn=time.sleep, extra_body=None):
        self._inner = inner
        self.chat = _Chat(inner.chat, sleep_fn, extra_body)

    def __getattr__(self, name):
        return getattr(self._inner, name)
