"""Runtime-tunable model names - DB-backed, admin-panel editable.

Provider model names (LLM, Embedding, OCR, Image, TTS) live here instead of in
Settings/.env, so the admin can switch them via the admin panel without a
server restart or .env editing.

Defaults are seeded into the DB on backend start (see schema.py).
"""

from src import database as db


# Single source of truth for default model names. On the first backend start
# these values are written into the settings table (see schema.py).
MODEL_DEFAULTS: dict[str, str] = {
    # LLM Chat
    "primary_llm_model": "mistral-large-3-675b-instruct-2512",
    "fallback_llm_model": "chat-default",
    "local_llm_model": "qwen3:8b",
    # LLM Translation (per-provider override for /translate; smaller/faster than chat)
    "translation_primary_model": "gemma-3-27b-it",
    "translation_fallback_model": "chat-default",
    "translation_local_model": "qwen3:8b",
    # Embeddings (AI assistant)
    "primary_embedding_model": "e5-mistral-7b-instruct",
    "fallback_embedding_model": "qwen3-embedding-4b",
    "local_embedding_model": "nomic-embed-text",
    # OCR
    "primary_ocr_model": "qwen3.5-122b-a10b",
    "fallback_ocr_model": "qwen3-vl-8b",
    # Image generation / editing (fallback slot only - primary slot has no equivalent today)
    "fallback_image_gen_model": "flux.1-dev",
    "fallback_image_edit_model": "flux.1-kontext",
    # TTS (slot identity = product name; not part of primary/fallback/local hierarchy)
    "mylab_tts_model": "tts-1-hd",
}

MODEL_KEYS: tuple[str, ...] = tuple(MODEL_DEFAULTS.keys())

# Subset of MODEL_DEFAULTS that gets seeded into the DB on first start.
# Keys *not* in this set are pure code-side defaults — they apply to every
# installation automatically when the default in code is bumped, instead of
# being frozen at install-time. DB stores user overrides only.
SEEDED_MODEL_KEYS: frozenset[str] = frozenset({
    "primary_llm_model",
    "fallback_llm_model",
    "local_llm_model",
    "primary_embedding_model",
    "fallback_embedding_model",
    "local_embedding_model",
    "primary_ocr_model",
    "fallback_ocr_model",
    "fallback_image_gen_model",
    "fallback_image_edit_model",
    "mylab_tts_model",
})


def get_model(key: str) -> str:
    """Read model name. Returns DB value if set, otherwise the code default."""
    if key not in MODEL_DEFAULTS:
        raise KeyError(f"Unknown model key: {key!r}")
    val = db.get_setting(key, "")
    if val:
        return val
    return MODEL_DEFAULTS[key]
