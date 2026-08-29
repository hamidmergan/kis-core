from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings from the environment, without provider credentials."""

    # Security
    session_secret: str = "change-me-in-production"

    # Must match the admin's LDAP address, it is unlocked at startup.
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

    # Unlocks the interface for creating LDAP users.
    ldap_user_creation_enabled: bool = False

    # Welche Module diese Anlage hat, Komma getrennt aus "aia" und "tools".
    modules: str = "aia,tools"

    # Key used to encrypt provider credentials on read and write.
    kis_export_key: str = ""

    @property
    def is_local_mode(self) -> bool:
        return not bool(self.ldap_server.strip())

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True}
