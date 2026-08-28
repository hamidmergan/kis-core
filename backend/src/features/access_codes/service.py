"""Pure rules around an access code, without database and without LDAP."""
import secrets
from datetime import datetime

# No 0, O, 1, I or L, the code gets read out on the phone.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_BLOCK_LENGTH = 4
DEMO_MAIL_DOMAIN = "demo.kis.local"


def new_code() -> str:
    """A code in the shape XXXX-XXXX."""
    bloecke = (
        "".join(secrets.choice(_ALPHABET) for _ in range(_BLOCK_LENGTH))
        for _ in range(2)
    )
    return "-".join(bloecke)


def normalize_code(text: str) -> str:
    """What the user typed, in the shape the database holds."""
    return (text or "").strip().upper()


def demo_email(uid: str) -> str:
    """The made-up address, LDAP and the whitelist both demand one."""
    return f"{uid}@{DEMO_MAIL_DOMAIN}"


def status_of(
    *,
    active: bool,
    used_count: int,
    max_uses: int,
    valid_until: datetime,
    now: datetime,
) -> str:
    """State of a code: active, disabled, expired or full."""
    if not active:
        return "disabled"
    if valid_until <= now:
        return "expired"
    if used_count >= max_uses:
        return "full"
    return "active"
