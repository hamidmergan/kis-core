"""Helper für den aktiven Embedding-Provider und Fingerprint-Cache.

Der Fingerprint ist das Embedding eines festen Sentinel-Strings. Er ist
deterministisch pro Provider/Modell und wird in der Settings-Tabelle persistiert,
damit er Backend-Neustarts überlebt (der erste Cold-Call gegen KISSKI dauert
15-50s, alle Folgeaufrufe sind instant).
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
    """Fingerprint aus Settings-Tabelle lesen; on-demand berechnen falls leer."""
    key = f"fingerprint_{active_embedding_provider_key()}"
    cached = db.get_setting(key, "") or ""
    if cached:
        return cached
    try:
        from src.services.kia_embeddings import compute_fingerprint, get_embedding_provider
        fp = compute_fingerprint(get_embedding_provider())
        db.set_setting(key, fp)
        return fp
    except Exception as e:
        logger.warning("Maintenance: fingerprint compute failed: {}", e)
        return None


def invalidate_fingerprint_cache() -> None:
    """Wird aufgerufen, wenn der Embedding-Provider-Toggle wechselt."""
    for provider in ("mylab", "kisski", "ollama", "default"):
        try:
            db.set_setting(f"fingerprint_{provider}", "")
        except Exception:
            pass
