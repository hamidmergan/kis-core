"""Password hashing for the database login, bcrypt for new hashes."""
import base64
import hashlib

import bcrypt

# bcrypt reads no further, a longer input would be cut without anybody noticing.
MAX_PASSWORD_BYTES = 72
_SSHA_PREFIX = "{SSHA}"
_SHA1_DIGEST_BYTES = 20


class PasswordTooLongError(ValueError):
    """The password does not fit into what bcrypt reads."""


def hash_password(password: str) -> str:
    """Returns a bcrypt hash, or raises when the password is beyond the limit."""
    roh = password.encode("utf-8")
    if len(roh) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(f"password exceeds {MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(roh, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, stored: str | None) -> bool:
    """True when the password fits the stored hash, bcrypt or a taken over SSHA one."""
    if not password or not stored:
        return False
    if stored.startswith(_SSHA_PREFIX):
        return _verify_ssha(password, stored)
    roh = password.encode("utf-8")
    if len(roh) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(roh, stored.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False


def _verify_ssha(password: str, stored: str) -> bool:
    """Checks the salted SHA1 that came over from the directory."""
    try:
        blob = base64.b64decode(stored[len(_SSHA_PREFIX):], validate=True)
    except (ValueError, TypeError):
        return False
    if len(blob) <= _SHA1_DIGEST_BYTES:
        return False
    digest, salt = blob[:_SHA1_DIGEST_BYTES], blob[_SHA1_DIGEST_BYTES:]
    return hashlib.sha1(password.encode("utf-8") + salt).digest() == digest


def needs_rehash(stored: str | None) -> bool:
    """True while the hash is still the old SSHA one."""
    return bool(stored) and stored.startswith(_SSHA_PREFIX)
