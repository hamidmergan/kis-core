from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Note: provider selection and model names are managed via the admin panel
    # (DB settings, see routes/admin/settings.py and services/runtime_models.py).
    # Only credentials/URLs and pure deployment stuff live here.

    # API Keys + Endpoints
    deepl_api_key: str = ""
    elevenlabs_api_key: str = ""

    # Primary OpenAI-compatible provider (today: KISSKI / GWDG Academic Cloud).
    # Legacy ENV names (KISSKI_API_KEY, KISSKI_BASE_URL) are accepted via
    # validation_alias so existing .env files keep working without edits.
    primary_provider_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("PRIMARY_PROVIDER_API_KEY", "KISSKI_API_KEY"),
    )
    primary_provider_base_url: str = Field(
        default="https://chat-ai.academiccloud.de/v1",
        validation_alias=AliasChoices("PRIMARY_PROVIDER_BASE_URL", "KISSKI_BASE_URL"),
    )

    # Fallback OpenAI-compatible provider (today: TH Lübeck myLab platform —
    # used for Whisper, embeddings, OCR, image gen/edit when admin toggles it).
    fallback_provider_base_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SECONDARY_PROVIDER_BASE_URL",
            "FALLBACK_PROVIDER_BASE_URL",
            "MYLAB_BASE_URL",
        ),
    )

    # Local OpenAI-compatible LLM/embedding provider (today: Ollama in Docker).
    local_provider_base_url: str = Field(
        default="http://ollama:11434/v1",
        validation_alias=AliasChoices("LOCAL_PROVIDER_BASE_URL", "OLLAMA_BASE_URL"),
    )

    # Kokoro TTS (Docker service, Apache 2.0): empty = disabled
    kokoro_base_url: str = ""

    # myLab TTS (TH Luebeck, Coqui XTTS-v2 via openedai-speech): empty = disabled.
    # Slot identity = product name; not part of the primary/fallback/local hierarchy.
    mylab_tts_base_url: str = ""

    # Security
    session_secret: str = "change-me-in-production"

    # Admin: email must match the LDAP account email of the admin user.
    # Auto-whitelisted on startup so first login works without manual DB edits.
    admin_email: str = ""

    # Set via start-nginx.sh / start-th.sh, never in .env
    production: bool = False

    # LDAP
    ldap_server: str = ""
    ldap_port: int = 389
    ldap_base_dn: str = ""
    ldap_bind_dn: str = ""
    ldap_bind_password: str = ""
    ldap_attr_username: str = "uid"
    ldap_attr_fullname: str = "cn"
    ldap_attr_email: str = "mail"
    ldap_attr_affiliation: str = "employeeType"
    ldap_role_lecturer_values: str = "staff,faculty"
    ldap_use_ssl: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True}
