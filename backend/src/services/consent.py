"""The one global notice every account accepts once, before any service is reachable."""

from src import database as db

GLOBAL_CONSENT_VERSION = 1


def has_global_consent(user_id: int | None) -> bool:
    if not user_id:
        return False
    version = db.get_global_consent(user_id).get("global_consent_version") or 0
    return version >= GLOBAL_CONSENT_VERSION
