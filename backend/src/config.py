from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DeepL
    deepl_api_key: str = ""
    translation_provider: str = "deepl"
    source_lang: str = "DE"
    target_lang: str = "EN-US"

    # Security
    kis_api_token: str = ""
    app_password: str = "admin"
    session_secret: str = "change-me-in-production"
    session_max_age_seconds: int = 86400  # 24h

    # CORS (comma-separated origins, only needed in development)
    cors_origins: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def effective_target_lang(self) -> str:
        raw = self.target_lang.strip().upper()
        if raw == "EN":
            return "EN-US"
        return raw

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
