"""What the provider, feature route and transfer routes share: the right, the shared row, the caps check."""

from fastapi import HTTPException

from src import database as db
from src.dependencies_rbac import require_permission
from src.features.ai_providers.repository.providers import CONCURRENCY_BUCKETS
from src.i18n import t
from src.permissions_registry import PERM_SET_PROVIDERS

# Providers, models and the mapping to the features, both tabs.
_require = require_permission(PERM_SET_PROVIDERS)

# Bounds of one cap, the upper one only catches typing mistakes.
_CONCURRENCY_MIN = 1
_CONCURRENCY_MAX = 1000


def _concurrency_problem(raw: dict) -> tuple[str, dict] | None:
    """Returns the message key and its parameters for the first invalid cap, or None."""
    unknown = sorted(str(k) for k in raw if k not in CONCURRENCY_BUCKETS)
    if unknown:
        return "admin.providers.concurrencyUnknownBucket", {"items": ", ".join(unknown)}
    for bucket, value in raw.items():
        if (value is not None and (isinstance(value, bool) or not isinstance(value, int)
                                   or not _CONCURRENCY_MIN <= value <= _CONCURRENCY_MAX)):
            return "admin.providers.concurrencyOutOfRange", {
                "bucket": bucket, "min": _CONCURRENCY_MIN, "max": _CONCURRENCY_MAX,
            }
    return None


def _check_concurrency(raw: dict | None, locale: str) -> dict | None:
    """Validates the caps of a provider, an empty value means no cap for that bucket."""
    if raw is None:
        return None
    problem = _concurrency_problem(raw)
    if problem:
        key, params = problem
        raise HTTPException(422, t(key, locale, **params))
    return {bucket: value for bucket, value in raw.items() if value is not None}


def _shared_provider(provider_id: int) -> dict | None:
    """A provider of the admin area, a person's own interface counts as not there."""
    row = db.get_provider(provider_id)
    if row is None or row.get("owner_user_id") is not None:
        return None
    return row


def _mask_provider(row: dict | None) -> dict | None:
    """Mask the raw api_key. The UI only ever sees the last 6 chars + a flag."""
    if row is None:
        return None
    masked = dict(row)
    raw = row.get("api_key")
    if raw:
        masked["api_key_set"] = True
        masked["api_key_last_chars"] = raw[-6:] if len(raw) > 6 else raw
    else:
        masked["api_key_set"] = False
        masked["api_key_last_chars"] = None
    masked.pop("api_key", None)
    return masked
