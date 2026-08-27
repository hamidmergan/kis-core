"""Detects whether an error is the provider's fault and not the input's."""

from __future__ import annotations

# Messages that mean the provider's service is behind it.
_BUSY_MARKERS = (
    "429", "rate limit", "too many requests",
    "500", "internal server error",
    "502", "503", "504",
    "bad gateway", "service unavailable", "gateway timeout",
    "timeout", "timed out",
)

# A key and not a finished sentence, the texts live in the frontend.
UPSTREAM_BUSY = "upstream_busy"


def is_upstream_busy(e: Exception | str) -> bool:
    """True when the provider was overloaded or did not answer."""
    msg = str(e).lower()
    return any(m in msg for m in _BUSY_MARKERS)


def upstream_error_code(e: Exception | str) -> str | None:
    """The key for the interface, or None when the provider is innocent."""
    return UPSTREAM_BUSY if is_upstream_busy(e) else None
