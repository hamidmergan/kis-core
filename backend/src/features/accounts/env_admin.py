"""The admin account from the .env, the way into a fresh installation."""
from loguru import logger

from src import database
from src.features.accounts.passwords import PasswordTooLongError, hash_password
from src.features.accounts.uid import slugify_uid, unique_uid

_FALLBACK_UID = "admin"


def ensure_env_admin(email: str, password: str) -> int | None:
    """Creates the admin once, an existing account keeps whatever password it has."""
    adresse = (email or "").strip().lower()
    if not adresse or not password:
        return None

    vorhanden = database.get_user_by_email(adresse)
    if vorhanden is not None:
        if not vorhanden.get("password_hash"):
            # A migrated account has no hash yet, the .env is its way back in.
            database.set_user_password(vorhanden["id"], _hash_or_none(password))
            logger.info("Admin from the .env got its password back")
        return vorhanden["id"]

    stamm = slugify_uid(adresse.split("@", 1)[0]) or _FALLBACK_UID
    name = unique_uid(stamm, lambda kandidat: database.get_user_by_username(kandidat) is not None)
    database.add_to_whitelist(adresse)
    user_id = database.create_user(
        ldap_username=name,
        display_name="Admin",
        email=adresse,
        active=1,
        role="admin",
        password_hash=_hash_or_none(password),
    )
    logger.info("Admin from the .env created (uid={})", name)
    return user_id


def _hash_or_none(password: str) -> str | None:
    """A password beyond the limit must not stop the start, it only stays unusable."""
    try:
        return hash_password(password)
    except PasswordTooLongError:
        logger.error("ADMIN_PASSWORD is too long, the admin gets no password")
        return None
