"""The active embedding provider and the stored fingerprint."""

from loguru import logger

from src import database as db


def active_embedding_provider_key() -> str:
    """Return a stable cache key for the embedding feature_route."""
    from src.services import feature_router
    try:
        binding = feature_router.resolve("embedding")
    except feature_router.FeatureNotConfigured:
        return "default"
    p = binding.provider
    return f"p{p['id']}_{(binding.model or '').replace('/', '_')}"


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
    """Deletes all fingerprint rows, the next call computes them again."""
    try:
        from src.core.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM settings WHERE key LIKE 'fingerprint_%'")
                conn.commit()
    except Exception as e:
        logger.warning("invalidate_fingerprint_cache failed: {}", e)
