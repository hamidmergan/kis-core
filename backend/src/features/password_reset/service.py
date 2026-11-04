"""Pure rules around password reset links, without database."""
import hashlib
import secrets
from datetime import datetime

from src.dependencies_rbac import permissions_of
from src.features.impersonation.service import FORBIDDEN_TARGET_KEYS, target_permissions
from src.permissions_registry import ROLE_ONLY_KEYS

VALID_DAYS = 14


def new_token() -> str:
    """The key in the reset link, 43 characters from 32 random bytes."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """The database keeps only this, so a leaked table gives no working link."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def can_get_reset_link(user: dict, env_admin_email: str = "") -> bool:
    """True for accounts with a bcrypt login that hold no right to manage users (created, invited, access code)."""
    if not (user.get("password_hash") or "").startswith("$2"):
        return False
    if user.get("role") == "admin":
        return False
    mail = (user.get("email") or "").lower()
    if mail and env_admin_email and mail == env_admin_email.lower():
        return False
    # Same line as the impersonation: whoever could hand out rights stays closed.
    return not target_permissions(user, env_admin_email).has(*FORBIDDEN_TARGET_KEYS)


def may_create_link(actor: dict, target: dict, env_admin_email: str = "") -> bool:
    """The target must be eligible, active, not the caller and hold nothing the caller lacks."""
    if not can_get_reset_link(target, env_admin_email):
        return False
    if not target.get("active"):
        return False
    if int(target.get("id") or 0) == int(actor.get("user_id") or 0):
        return False
    actor_keys = permissions_of(actor).keys
    beyond = [
        k for k in target_permissions(target, env_admin_email).keys
        if k not in actor_keys and k not in ROLE_ONLY_KEYS
    ]
    return not beyond


def status_of(*, used_at: datetime | None, expires_at: datetime, now: datetime) -> str:
    """State of a reset link: open, used or expired."""
    if used_at is not None:
        return "used"
    if expires_at <= now:
        return "expired"
    return "open"
