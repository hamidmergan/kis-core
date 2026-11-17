"""Checking a name or a mail address plus password against the database."""
import secrets
from functools import lru_cache

from loguru import logger

from src import database
from src.features.accounts.passwords import (
    MAX_PASSWORD_BYTES,
    hash_password,
    needs_rehash,
    verify_password,
)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """A bcrypt hash of a secret nobody knows, made once per process."""
    return hash_password(secrets.token_urlsafe(24))


def find_user(kennung: str):
    """A mail address carries an @, a user name never does, so no guessing is needed."""
    wert = (kennung or "").strip()
    if not wert:
        return None
    if "@" in wert:
        return database.get_user_by_email(wert)
    return database.get_user_by_username(wert)


def authenticate(kennung: str, passwort: str):
    """Returns the account on a matching password, None otherwise."""
    konto = find_user(kennung)
    gespeichert = konto["password_hash"] if konto is not None else None
    # An unknown name costs the same hashing time as a wrong password, so timing names no account.
    if not verify_password(passwort, gespeichert or _dummy_hash()) or not gespeichert:
        return None
    if needs_rehash(gespeichert) and len(passwort.encode("utf-8")) <= MAX_PASSWORD_BYTES:
        database.set_user_password(konto["id"], hash_password(passwort))
        logger.info("Password of user {} moved to the new hashing", konto["id"])
    return konto
