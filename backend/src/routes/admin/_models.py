"""Pydantic models for admin endpoints."""

from pydantic import BaseModel


class AddWhitelistRequest(BaseModel):
    email: str


class UpdateSettingsRequest(BaseModel):
    whitelist_enabled: bool | None = None
    # TTS
    elevenlabs_enabled: bool | None = None
    kokoro_enabled: bool | None = None
    mylab_enabled: bool | None = None
    # Transcription
    primary_whisper_enabled: bool | None = None
    fallback_whisper_enabled: bool | None = None
    # Embeddings
    primary_embedding_enabled: bool | None = None
    fallback_embedding_enabled: bool | None = None
    local_embedding_enabled: bool | None = None
    # Image generation
    primary_image_gen_enabled: bool | None = None
    fallback_image_gen_enabled: bool | None = None
    # Image analysis (primary: KISSKI qwen3-omni, fallback: myLab qwen3-vl)
    primary_image_analyze_enabled: bool | None = None
    fallback_image_analyze_enabled: bool | None = None
    # Image editing
    primary_image_edit_enabled: bool | None = None
    fallback_image_edit_enabled: bool | None = None
    # OCR
    primary_ocr_enabled: bool | None = None
    fallback_ocr_enabled: bool | None = None
    # LLM Chat
    primary_llm_enabled: bool | None = None
    fallback_llm_enabled: bool | None = None
    local_llm_enabled: bool | None = None
    # Transcript translation (EN)
    transcript_translation_provider: str | None = None
    # /translate LLM provider override (empty = use active LLM)
    # Model values flow through the generic `models` dict (see MODEL_KEYS).
    translation_llm_provider: str | None = None  # "" | "primary" | "fallback" | "local"
    # Provider model names (DB setting). Allowed keys: see runtime_models.MODEL_KEYS.
    models: dict[str, str] | None = None
    # UI label for "Workspace" (singular + plural), per UI locale.
    workspace_label_singular_de: str | None = None
    workspace_label_plural_de: str | None = None
    workspace_label_singular_en: str | None = None
    workspace_label_plural_en: str | None = None
    # Hide the Hilde mascot system-wide. Default true (mascot shown).
    mascot_enabled: bool | None = None


class ToggleToolRequest(BaseModel):
    enabled: bool


class MaintenanceToggleRequest(BaseModel):
    enabled: bool


class UpdatePromptRequest(BaseModel):
    value: str


class SetQuotaOverrideRequest(BaseModel):
    limit_value: int  # -1 = unlimited
