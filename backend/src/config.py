from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Process-level configuration sourced from the environment.

    Provider credentials + URLs (LLM, embedding, TTS, OCR, DeepL, ...) are
    NOT here — they live in the ``providers`` table managed by the admin
    "KI" tab. Only deployment-level stuff (DB, S3, sessions, LDAP) stays.
    """

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

    # Admin-only feature flag: enables UI for creating LDAP users.
    # Disable on prod / SSO deployments.
    ldap_user_creation_enabled: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True}
