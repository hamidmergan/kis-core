"""Helper for the active embedding provider and fingerprint cache.

The fingerprint is the embedding of a fixed sentinel string. It is
deterministic per provider/model and is persisted in the settings table,
so it survives backend restarts (the first cold call against a remote
provider takes 15-50s, all subsequent calls are instant).
"""

from loguru import logger

from src import database as db


def active_embedding_provider_key() -> str:
    if db.get_setting("fallback_embedding_enabled", "false").lower() == "true":
        return "fallback"
    if db.get_setting("primary_embedding_enabled", "false").lower() == "true":
        return "primary"
    if db.get_setting("local_embedding_enabled", "false").lower() == "true":
        return "local"
    return "default"


def get_cached_fingerprint() -> str | None:
    """Read fingerprint from settings table; compute on demand if empty."""
    key = f"fingerprint_{active_embedding_provider_key()}"
    cached = db.get_setting(key, "") or ""
    if cached:
        return cached
    try:
        from src.services.aia_embeddings import compute_fingerprint, get_embedding_provider
        fp = compute_fingerprint(get_embedding_provider())
        db.set_setting(key, fp)
        return fp
    except Exception as e:
        logger.warning("Maintenance: fingerprint compute failed: {}", e)
        return None


def invalidate_fingerprint_cache() -> None:
    """Called when the embedding provider toggle changes."""
    # Includes legacy provider names so that fingerprints persisted by older
    # backend versions get cleared on the next admin toggle as well.
    for provider in ("primary", "fallback", "local", "default", "kisski", "mylab", "ollama"):
        try:
            db.set_setting(f"fingerprint_{provider}", "")
        except Exception:
            pass
