from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Translation
    translation_languages: str = "DE,EN-US,FR,ES,IT"

    # Note: provider selection and model names are managed via the admin panel
    # (DB settings, see routes/admin/settings.py and services/runtime_models.py).
    # Only credentials/URLs and pure deployment stuff live here.

    # API Keys + Endpoints
    deepl_api_key: str = ""
    elevenlabs_api_key: str = ""
    kisski_api_key: str = ""
    kisski_base_url: str = "https://chat-ai.academiccloud.de/v1"

    # Ollama (local)
    ollama_base_url: str = "http://ollama:11434/v1"

    # Fish Speech TTS (local TTS server): empty = disabled
    fish_speech_base_url: str = ""

    # Kokoro TTS (Docker service, Apache 2.0): empty = disabled
    kokoro_base_url: str = ""
    kokoro_api_key: str = ""

    # myLab TTS (TH Luebeck, Coqui XTTS-v2): empty = disabled
    mylab_tts_base_url: str = ""

    # myLab platform (TH Luebeck): shared base URL for Whisper, Image, Embeddings, OCR
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
