"""Runtime-tunable model names — DB-backed, admin-panel editable.

Provider-Modellnamen (LLM, Embedding, OCR, Image, TTS) leben hier statt in
Settings/.env, damit der Admin sie ueber das Admin-Panel wechseln kann ohne
Server-Neustart oder .env-Editing.

Defaults werden beim Backend-Start in die DB geseedet (siehe schema.py).
"""

from src import database as db


# Single source of truth for default model names. Beim ersten Backend-Start
# werden diese Werte in die settings-Tabelle geschrieben (siehe schema.py).
MODEL_DEFAULTS: dict[str, str] = {
    # LLM Chat
    "kisski_llm_model": "mistral-large-3-675b-instruct-2512",
    "mylab_llm_model": "chat-default",
    "ollama_llm_model": "qwen3:8b",
    # Embeddings (KI-Assistent)
    "kisski_embedding_model": "e5-mistral-7b-instruct",
    "mylab_embedding_model": "qwen3-embedding-4b",
    "ollama_embedding_model": "nomic-embed-text",
    # OCR
    "kisski_ocr_model": "qwen3.5-122b-a10b",
    "mylab_ocr_model": "qwen3-vl-8b",
    # Bild-Generierung / -Bearbeitung (myLab only)
    "mylab_image_gen_model": "flux.1-dev",
    "mylab_image_edit_model": "flux.1-kontext",
    # TTS
    "mylab_tts_model": "tts-1-hd",
}

MODEL_KEYS: tuple[str, ...] = tuple(MODEL_DEFAULTS.keys())


def get_model(key: str) -> str:
    """Read model name from DB. Falls back to MODEL_DEFAULTS if not seeded yet
    (e.g. during initial migration before schema bootstrap completes).
    """
    if key not in MODEL_DEFAULTS:
        raise KeyError(f"Unknown model key: {key!r}")
    val = db.get_setting(key, "")
    if val:
        return val
    return MODEL_DEFAULTS[key]
