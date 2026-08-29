"""Pure rules around invitations, without database and without LDAP."""
import secrets
from datetime import datetime

from src.features.accounts.uid import slugify_uid

INVITE_MAIL_DOMAIN = "kis.local"


class InviteValidationError(ValueError):
    """The input is not fit for an invitation."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


def uid_from_username(text: str) -> str:
    """Turns what the inviting person typed into a user name LDAP accepts."""
    uid = slugify_uid(text)
    if uid is None:
        raise InviteValidationError("username", "yields no usable uid")
    return uid


def invite_email(uid: str) -> str:
    """The made-up address, LDAP and the whitelist both demand one."""
    return f"{uid}@{INVITE_MAIL_DOMAIN}"


def new_token() -> str:
    """The key in the invitation link, 43 characters from 32 random bytes."""
    return secrets.token_urlsafe(32)


def status_of(*, used_at: datetime | None, expires_at: datetime, now: datetime) -> str:
    """State of an invitation: open, used or expired."""
    if used_at is not None:
        return "used"
    if expires_at <= now:
        return "expired"
    return "open"
