from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Translation
    source_lang: str = "DE"
    target_lang: str = "EN-US"
    translation_provider: str = "deepl"  # "deepl" oder "llm"
    translation_languages: str = "DE,EN-US,FR,ES,IT"

    # API Keys (stored in .env)
    deepl_api_key: str = ""
    elevenlabs_api_key: str = ""
    kisski_api_key: str = ""
    kisski_base_url: str = "https://chat-ai.academiccloud.de/v1"
    kisski_model: str = "qwen3-30b-a3b-instruct-2507"
    kisski_embedding_model: str = "e5-mistral-7b-instruct"
    tutor_embedding_provider: str = "kisski"
    ollama_embedding_model: str = "nomic-embed-text"

    # LLM Provider: "kisski" oder "ollama"
    llm_provider: str = "kisski"
    ollama_base_url: str = "http://ollama:11434/v1"
    ollama_model: str = "qwen3:30b-a3b"

    # Fish Speech TTS (lokaler TTS-Server) — leer = deaktiviert
    fish_speech_base_url: str = ""

    # Kokoro TTS (Docker Service, Apache 2.0) — leer = deaktiviert
    kokoro_base_url: str = ""
    kokoro_api_key: str = ""

    # myLab TTS (TH Lübeck, Coqui XTTS-v2) — leer = deaktiviert
    mylab_tts_base_url: str = ""
    mylab_tts_model: str = "tts-1-hd"

    # Thorsten TTS (lokaler Docker, Coqui VITS) — leer = deaktiviert
    thorsten_base_url: str = ""

    # myLab Plattform (TH Lübeck) — gemeinsame Base-URL für Whisper, Image, Embeddings, OCR
    mylab_base_url: str = ""

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def effective_target_lang(self) -> str:
        raw = self.target_lang.strip().upper()
        if raw == "EN":
            return "EN-US"
        return raw

    @property
    def effective_llm_api_key(self) -> str:
        if self.llm_provider == "ollama":
            return "ollama"
        return self.kisski_api_key

    @property
    def effective_llm_base_url(self) -> str:
        if self.llm_provider == "ollama":
            return self.ollama_base_url
        return self.kisski_base_url

    @property
    def effective_llm_model(self) -> str:
        if self.llm_provider == "ollama":
            return self.ollama_model
        return self.kisski_model

