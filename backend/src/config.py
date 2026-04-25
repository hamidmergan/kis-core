from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Translation
    translation_languages: str = "DE,EN-US,FR,ES,IT"

    # Hinweis: Provider-Auswahl + Modellnamen werden ueber das Admin-Panel verwaltet
    # (DB-Settings, siehe routes/admin/settings.py und services/runtime_models.py).
    # Hier liegen nur Credentials/URLs und reines Deployment-Stuff.

    # API Keys + Endpoints
    deepl_api_key: str = ""
    elevenlabs_api_key: str = ""
    kisski_api_key: str = ""
    kisski_base_url: str = "https://chat-ai.academiccloud.de/v1"

    # Ollama (lokal)
    ollama_base_url: str = "http://ollama:11434/v1"

    # Fish Speech TTS (lokaler TTS-Server) — leer = deaktiviert
    fish_speech_base_url: str = ""

    # Kokoro TTS (Docker Service, Apache 2.0) — leer = deaktiviert
    kokoro_base_url: str = ""
    kokoro_api_key: str = ""

    # myLab TTS (TH Lübeck, Coqui XTTS-v2) — leer = deaktiviert
    mylab_tts_base_url: str = ""

    # Thorsten TTS (lokaler Docker, Coqui VITS) — leer = deaktiviert
    thorsten_base_url: str = ""

    # myLab Plattform (TH Lübeck) — gemeinsame Base-URL fuer Whisper, Image, Embeddings, OCR
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
