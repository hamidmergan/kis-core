"""Checking a name or a mail address plus password against the database."""
from loguru import logger

from src import database
from src.features.accounts.passwords import (
    MAX_PASSWORD_BYTES,
    hash_password,
    needs_rehash,
    verify_password,
)


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
    if konto is None:
        return None
    gespeichert = konto["password_hash"]
    if not verify_password(passwort, gespeichert):
        return None
    if needs_rehash(gespeichert) and len(passwort.encode("utf-8")) <= MAX_PASSWORD_BYTES:
        database.set_user_password(konto["id"], hash_password(passwort))
        logger.info("Password of user {} moved to the new hashing", konto["id"])
    return konto
