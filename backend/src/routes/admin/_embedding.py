"""Helper for the active embedding provider and fingerprint cache.

The fingerprint is the embedding of a fixed sentinel string. It is
deterministic per provider/model and is persisted in the settings table,
so it survives backend restarts (the first cold call against KISSKI takes
15-50s, all subsequent calls are instant).
"""

from loguru import logger

from src import database as db


def active_embedding_provider_key() -> str:
    if db.get_setting("mylab_embedding_enabled", "false").lower() == "true":
        return "mylab"
    if db.get_setting("kisski_embedding_enabled", "false").lower() == "true":
        return "kisski"
    if db.get_setting("ollama_embedding_enabled", "false").lower() == "true":
        return "ollama"
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
    for provider in ("mylab", "kisski", "ollama", "default"):
        try:
            db.set_setting(f"fingerprint_{provider}", "")
        except Exception:
            pass
