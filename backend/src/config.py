from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings from the environment, without provider credentials."""

    # Security
    session_secret: str = "change-me-in-production"

    # The admin account, created on start and unlocked right away.
    admin_email: str = ""

    # The admin's password, only read on start and never written back.
    admin_password: str = ""

    # Set via start-nginx.sh / start-th.sh, never in .env
    production: bool = False

    # Unlocks invitations, access codes and creating accounts by hand.
    account_creation_enabled: bool = False

    # No login screen at all, everybody is the local admin. Local use only.
    auth_disabled: bool = False

    # Which halves this installation has, comma separated from "aia" and "tools".
    modules: str = "aia,tools"

    # Key used to encrypt provider credentials on read and write.
    kis_export_key: str = ""

    @property
    def is_local_mode(self) -> bool:
        return self.auth_disabled

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True}
