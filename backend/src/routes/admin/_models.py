"""Pydantic models for admin endpoints."""

from pydantic import BaseModel


class AddWhitelistRequest(BaseModel):
    email: str


class UpdateSettingsRequest(BaseModel):
    whitelist_enabled: bool | None = None
    # TTS
    elevenlabs_enabled: bool | None = None
    fish_speech_enabled: bool | None = None
    kokoro_enabled: bool | None = None
    mylab_enabled: bool | None = None
    # Transcription
    kisski_whisper_enabled: bool | None = None
    mylab_whisper_enabled: bool | None = None
    # Embeddings
    kisski_embedding_enabled: bool | None = None
    mylab_embedding_enabled: bool | None = None
    ollama_embedding_enabled: bool | None = None
    # Image generation
    kisski_image_gen_enabled: bool | None = None
    mylab_image_gen_enabled: bool | None = None
    # Image analysis (KISSKI only)
    kisski_image_analyze_enabled: bool | None = None
    # Image editing
    kisski_image_edit_enabled: bool | None = None
    mylab_image_edit_enabled: bool | None = None
    # OCR
    kisski_ocr_enabled: bool | None = None
    mylab_ocr_enabled: bool | None = None
    # LLM Chat
    kisski_llm_enabled: bool | None = None
    mylab_llm_enabled: bool | None = None
    ollama_llm_enabled: bool | None = None
    # Transcript translation (EN)
    transcript_translation_provider: str | None = None
    # Provider model names (DB setting). Allowed keys: see runtime_models.MODEL_KEYS.
    models: dict[str, str] | None = None


class ToggleToolRequest(BaseModel):
    enabled: bool


class MaintenanceToggleRequest(BaseModel):
    enabled: bool


class UpdatePromptRequest(BaseModel):
    value: str


class SetQuotaOverrideRequest(BaseModel):
    limit_value: int  # -1 = unlimited
