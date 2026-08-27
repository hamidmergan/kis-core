"""Pure rules around invitations, without database and without LDAP."""
import re
import secrets
from datetime import datetime

_UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
_UNERLAUBT = re.compile(r"[^a-z0-9_.-]")
_UID = re.compile(r"^[a-z0-9_.-]{2,32}$")


class InviteValidationError(ValueError):
    """The input is not fit for an invitation."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


def uid_from_email(email: str) -> str:
    """Derives the user name from the part before the @."""
    lokal = email.split("@", 1)[0].strip().lower()
    for zeichen, ersatz in _UMLAUTE.items():
        lokal = lokal.replace(zeichen, ersatz)
    uid = _UNERLAUBT.sub("", lokal)
    if not _UID.match(uid):
        raise InviteValidationError("email", "local part yields no usable uid")
    return uid


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
