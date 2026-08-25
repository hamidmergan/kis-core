"""Reine Regeln rund um Einladungen, ohne Datenbank und ohne LDAP."""
import re
import secrets
from datetime import datetime

_UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
_UNERLAUBT = re.compile(r"[^a-z0-9_.-]")
_UID = re.compile(r"^[a-z0-9_.-]{2,32}$")


class InviteValidationError(ValueError):
    """Die Eingabe taugt nicht fuer eine Einladung."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


def uid_from_email(email: str) -> str:
    """Leitet den Benutzernamen aus dem Teil vor dem @ ab."""
    lokal = email.split("@", 1)[0].strip().lower()
    for zeichen, ersatz in _UMLAUTE.items():
        lokal = lokal.replace(zeichen, ersatz)
    uid = _UNERLAUBT.sub("", lokal)
    if not _UID.match(uid):
        raise InviteValidationError("email", "local part yields no usable uid")
    return uid


def new_token() -> str:
    """Der Schluessel im Einladungslink, 43 Zeichen aus 32 Zufallsbytes."""
    return secrets.token_urlsafe(32)


def status_of(*, used_at: datetime | None, expires_at: datetime, now: datetime) -> str:
    """Zustand einer Einladung: open, used oder expired."""
    if used_at is not None:
        return "used"
    if expires_at <= now:
        return "expired"
    return "open"
