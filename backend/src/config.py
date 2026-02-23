from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DeepL
    deepl_api_key: str = ""
    translation_provider: str = "deepl"
    source_lang: str = "DE"
    target_lang: str = "EN-US"

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # KISSKI LLM (OpenAI-compatible)
    kisski_api_key: str = ""
    kisski_base_url: str = "https://chat-ai.academiccloud.de/v1"
    kisski_model: str = "qwen3-30b-a3b-instruct-2507"

    # Security
    app_password: str = "admin"
    session_secret: str = "change-me-in-production"
    session_max_age_seconds: int = 86400  # 24h

    # Demo mode: serve pre-built demo data instead of calling external APIs
    demo_data: bool = False

    # Environment: set True on server, False for local dev
    production: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def effective_target_lang(self) -> str:
        raw = self.target_lang.strip().upper()
        if raw == "EN":
            return "EN-US"
        return raw

