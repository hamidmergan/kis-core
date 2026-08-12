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
    # Offer the Sprachtrainer system-wide. Default false: without it, workspace
    # owners never see the switch and nobody gets the trainer.
    language_training_enabled: bool | None = None
    # Home-page notice banner (shown to all users on the start page, above
    # "Nächste Termine"). Enabled flag + free text, e.g. for test-phase notes.
    home_notice_enabled: bool | None = None
    home_notice_text: str | None = None
    # Run OCR on image-heavy PDF/slide pages during indexing. Default true.
    # Off = skip all OCR (faster + cheaper, but scanned pages stay un-indexed).
    ocr_enabled: bool | None = None
    # Per-workspace source upload cap (admin-tunable, default 30).
    aia_workspace_max_sources: int | None = None
    # KI-tutor chat context budget in characters. Drives both the truncation in
    # the context builder and the "full document fits -> send it whole" overview
    # path. Sized for the smallest supported model (32k) by default; a deployment
    # on large-context models can raise it.
    aia_context_max_chars: int | None = None
    # Context budget (chars) for the GENERATION TOOLS (mindmap, data table, quiz,
    # flashcards, …). Separate from the chat budget so the tools can get a larger
    # window; divided by the number of selected sources at generation time.
    aia_tool_context_max_chars: int | None = None
    # Per-batch char cap for the ingest-side DOC SUMMARY. Bigger = fewer (but
    # coarser) summary calls per upload → fewer GWDG-rate-limited requests.
    aia_summary_batch_max_chars: int | None = None
    # Max pages per uploaded source (long scripts → upload chapter-wise). Keeps a
    # source near the fit-shortcut size so its overview stays complete.
    aia_source_max_pages: int | None = None
    # Aussprache auf der Lernkarte: welcher TTS-Anbieter spricht und mit welcher
    # Stimme. Als Zeichenkette, weil die leere Wahl "nicht eingerichtet" heißt und
    # eine Zahl das nicht ausdrücken kann. Das Modell steht nicht hier, es kommt
    # aus der Route "Text in Sprache".
    aia_flashcard_voice_provider_id: str | None = None
    aia_flashcard_voice_id: str | None = None
    # Nebenläufigkeit steht hier bewusst NICHT mehr. Platzanzahl, gleichzeitige
    # Uploads und Umwandlungs-Threads werden an der Maschine gemessen
    # (services/system_capacity.py), Vertonung und Spracherkennung sind gemessene
    # Konstanten in limits.py. Beides sind Fragen, die ein Mensch im
    # Admin-Bereich nicht beantworten kann.
    tts_max_chars_per_request: int | None = None
    # System prompt for the CEFR chat diagnosis. ONE prompt for every language;
    # the workspace language is substituted for the {language} placeholder. An
    # empty string restores the shipped default.
    language_diagnosis_prompt: str | None = None
    # Question plan as a JSON string (list of {"type","text"?}). Empty string
    # restores the shipped default plan.
    language_diagnosis_question_plan_de: str | None = None
    # Soft UI cap for the diagnosis answer length (chars). Hard-capped server-side
    # to MAX_MESSAGE_CHARS.
    language_diagnosis_answer_max_chars: int | None = None
    # Adaptive answer behaviour for the existing workspace chat. Empty string
    # restores the shipped default.
    language_diagnosis_adaptive_behavior: str | None = None
    # Grading rules (LEVEL ASSIGNMENT). Empty string restores the shipped default.
    language_diagnosis_grading_rules: str | None = None
    # Per-level calibration examples as a JSON object {"A1":..,..,"C1":..,"C2":..}.
    # Empty string restores the shipped defaults.
    language_diagnosis_level_examples: str | None = None
    # Beschreibung je Stufe als JSON-Objekt {"A1":..,..,"C2":..}. Leerer String
    # setzt auf die ausgelieferten Standards zurueck.
    language_diagnosis_level_descriptions: str | None = None


class ToggleToolRequest(BaseModel):
    enabled: bool


class MaintenanceToggleRequest(BaseModel):
    enabled: bool


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
    provider_models: dict[str, str] | None = None  # per-provider model overrides


# ─── Export/Import schema ──────────────────────────────────────────────────

class ExportedProvider(BaseModel):
    name: str
    protocol: str
    base_url: str
    capabilities: list[str] = []
    voices: list[VoiceEntry] = []
    enabled: bool = True
    # AES-GCM envelope produced by export_crypto.wrap_api_key, or None when
    # the source instance had no KIS_EXPORT_KEY configured / no key on file.
    api_key: dict | None = None


class ExportedFeatureRoute(BaseModel):
    feature: str
    provider_name: str | None = None
    model_name: str | None = None
    user_choices: list[str] = []
    provider_models: dict[str, str] = {}


class ExportedConfig(BaseModel):
    schema_version: int
    exported_at: str
    exported_from: str | None = None
    providers: list[ExportedProvider] = []
    feature_routes: list[ExportedFeatureRoute] = []


class ImportConfigRequest(BaseModel):
    config: ExportedConfig
