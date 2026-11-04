"""Pure rules around password reset links, without database."""
import hashlib
import secrets
from datetime import datetime

VALID_DAYS = 14


def new_token() -> str:
    """The key in the reset link, 43 characters from 32 random bytes."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """The database keeps only this, so a leaked table gives no working link."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def can_get_reset_link(user: dict, env_admin_email: str = "") -> bool:
    """True for accounts with a bcrypt login that are not an admin (created, invited, access code)."""
    if not (user.get("password_hash") or "").startswith("$2"):
        return False
    if user.get("role") == "admin":
        return False
    mail = (user.get("email") or "").lower()
    return not (mail and env_admin_email and mail == env_admin_email.lower())


def status_of(*, used_at: datetime | None, expires_at: datetime, now: datetime) -> str:
    """State of a reset link: open, used or expired."""
    if used_at is not None:
        return "used"
    if expires_at <= now:
        return "expired"
    return "open"
