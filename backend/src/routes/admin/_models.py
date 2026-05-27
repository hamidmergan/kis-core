"""Pydantic models for admin endpoints."""

from pydantic import BaseModel


class AddWhitelistRequest(BaseModel):
    email: str


class UpdateSettingsRequest(BaseModel):
    """System-wide settings the admin can edit from the "System" tab.

    Provider selection, model names, and feature routing live in the dedicated
    "KI" admin tab (providers + feature_routes tables); they are NOT part of
    this payload.
    """
    whitelist_enabled: bool | None = None
    # UI label for "Workspace" (singular + plural), per UI locale.
    workspace_label_singular_de: str | None = None
    workspace_label_plural_de: str | None = None
    workspace_label_singular_en: str | None = None
    workspace_label_plural_en: str | None = None
    # Hide the Hilde mascot system-wide. Default true (mascot shown).
    mascot_enabled: bool | None = None
    # Per-workspace source upload cap (admin-tunable, default 30).
    aia_workspace_max_sources: int | None = None
    # Schedule entries older than this many days are pruned daily.
    # 0 = never delete (default). Bounded to a sane upper limit.
    aia_schedule_retention_days: int | None = None


class ToggleToolRequest(BaseModel):
    enabled: bool


class MaintenanceToggleRequest(BaseModel):
    enabled: bool


class UpdatePromptRequest(BaseModel):
    value: str


class SetQuotaOverrideRequest(BaseModel):
    limit_value: int  # -1 = unlimited


class VoiceEntry(BaseModel):
    voice_id: str
    name: str
    language: str               # required – e.g. "de", "en"
    description: str | None = None


class CreateProviderRequest(BaseModel):
    name: str
    protocol: str
    base_url: str
    api_key: str | None = None
    voices: list[VoiceEntry] = []
    enabled: bool = True
    initial_capabilities: list[str] | None = None  # if set, skips probe-seeding


class UpdateProviderRequest(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # empty string clears the key
    capabilities: list[str] | None = None  # admin override after probe
    voices: list[VoiceEntry] | None = None
    enabled: bool | None = None


class DiscoverVoicesRequest(BaseModel):
    base_url: str
    api_key: str | None = None
    voices_path: str | None = None  # default: /v1/audio/voices


class SetFeatureRouteRequest(BaseModel):
    provider_id: int | None = None  # null clears the route
    model_name: str | None = None
    user_choices: list[int] | None = None  # multi-pill provider ids
