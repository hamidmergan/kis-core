"""Detects whether an error is the provider's fault and not the input's."""

from __future__ import annotations

import re

# Messages that mean the provider's service is behind it.
_BUSY_MARKERS = (
    "429", "rate limit", "too many requests",
    "500", "internal server error",
    "502", "503", "504",
    "bad gateway", "service unavailable", "gateway timeout",
    "timeout", "timed out",
    # The provider could not be reached for a moment, a lost connection or a failed name lookup.
    "connection error", "temporary failure in name resolution",
)

# A key and not a finished sentence, the texts live in the frontend.
UPSTREAM_BUSY = "upstream_busy"


def is_upstream_busy(e: Exception | str) -> bool:
    """True when the provider was overloaded or did not answer."""
    if is_provider_refusal(e):
        return False
    msg = str(e).lower()
    return any(m in msg for m in _BUSY_MARKERS)


def upstream_error_code(e: Exception | str) -> str | None:
    """The key for the interface, or None when the provider is innocent."""
    return UPSTREAM_BUSY if is_upstream_busy(e) else None


# Answers that stay the same however often the job asks again.
_REFUSAL_STATUSES = frozenset({400, 401, 403, 404})
_REFUSAL_TEXT = re.compile(r"(?:error code|client error)[: ']+(40[0134])\b")


def _status_of(e: BaseException) -> int | None:
    """The HTTP status an SDK or httpx error carries, None without one."""
    code = getattr(e, "status_code", None)
    if code is None:
        code = getattr(getattr(e, "response", None), "status_code", None)
    return code if isinstance(code, int) else None


def is_provider_refusal(e: BaseException | str) -> bool:
    """True when the provider turned the call down for good, a wrong key, a missing model or a rejected request."""
    if isinstance(e, str):
        return bool(_REFUSAL_TEXT.search(e.lower()))
    seen: set[int] = set()
    cur: BaseException | None = e
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if _status_of(cur) in _REFUSAL_STATUSES or _REFUSAL_TEXT.search(str(cur).lower()):
            return True
        cur = cur.__cause__ or cur.__context__
    return False
