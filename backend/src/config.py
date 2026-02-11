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

    # Docs (Swagger UI) – only enable in development
    enable_docs: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def effective_target_lang(self) -> str:
        raw = self.target_lang.strip().upper()
        if raw == "EN":
            return "EN-US"
        return raw

