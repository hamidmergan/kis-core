"""Admin-only LDAP user creation. Behind LDAP_USER_CREATION_ENABLED feature flag.

This module is a temporary bridge for local dev and the Hetzner box. It will
be retired once THL SSO is wired up.
"""
import base64
import hashlib
import os
import re
import secrets

from ldap3 import NONE, Connection, Server
from ldap3.core.exceptions import LDAPException

from src.config import Settings


_UID_RE = re.compile(r"^[a-z0-9_.-]{2,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_EMPLOYEE_TYPES = ("staff", "student")


class LdapValidationError(ValueError):
    """Raised when input does not pass uid/email/employee_type rules."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


class LdapUserExistsError(Exception):
    """Raised when the uid already exists in the directory."""


class LdapServiceError(RuntimeError):
    """Raised on bind failures or unexpected LDAP add errors."""


def _make_ssha_hash(password: str) -> str:
    """Return an OpenLDAP-compatible {SSHA} hash for `password`.

    Format: '{SSHA}' + base64( sha1(password + salt) + salt ),
    salt is 4 random bytes (matches OpenLDAP defaults).
    """
    salt = os.urandom(4)
    digest = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return "{SSHA}" + base64.b64encode(digest + salt).decode("ascii")


def _generate_password() -> str:
    """16-char URL-safe random token (~95 bits of entropy)."""
    return secrets.token_urlsafe(12)


def validate_inputs(
    *, uid: str, given_name: str, surname: str, email: str, employee_type: str
) -> None:
    if not _UID_RE.match(uid or ""):
        raise LdapValidationError("uid", "must match ^[a-z0-9_.-]{2,32}$")
    if not (given_name or "").strip():
        raise LdapValidationError("given_name", "required")
    if not (surname or "").strip():
        raise LdapValidationError("surname", "required")
    if not _EMAIL_RE.match(email or ""):
        raise LdapValidationError("email", "invalid email format")
    if employee_type not in _VALID_EMPLOYEE_TYPES:
        raise LdapValidationError("employee_type", f"must be one of {_VALID_EMPLOYEE_TYPES}")


def create_ldap_user(
    *,
    settings: Settings,
    uid: str,
    given_name: str,
    surname: str,
    email: str,
    employee_type: str,
) -> str:
    """Add an inetOrgPerson under ou=people. Return the generated plain password.

    The password is hashed to {SSHA} before it leaves this function.
    The plaintext is returned to the caller exactly once and must NOT be logged
    or persisted.
    """
    validate_inputs(
        uid=uid,
        given_name=given_name,
        surname=surname,
        email=email,
        employee_type=employee_type,
    )

    plain_password = _generate_password()
    hashed = _make_ssha_hash(plain_password)
    dn = f"uid={uid},ou=people,{settings.ldap_base_dn}"
    attrs = {
        "uid": uid,
        "cn": f"{given_name.strip()} {surname.strip()}",
        "sn": surname.strip(),
        "mail": email,
        "userPassword": hashed,
        "employeeType": employee_type,
    }

    server = Server(
        settings.ldap_server,
        port=settings.ldap_port,
        use_ssl=settings.ldap_use_ssl,
        get_info=NONE,
    )
    try:
        conn = Connection(
            server,
            user=settings.ldap_bind_dn,
            password=settings.ldap_bind_password,
            auto_bind=True,
        )
    except LDAPException as e:
        raise LdapServiceError(f"LDAP service bind failed: {e}") from e

    try:
        ok = conn.add(dn, ["inetOrgPerson"], attrs)
        if ok:
            return plain_password

        desc = (conn.result or {}).get("description", "")
        if desc == "entryAlreadyExists":
            raise LdapUserExistsError(uid)
        raise LdapServiceError(f"LDAP add failed: {desc or conn.result!r}")
    finally:
        try:
            conn.unbind()
        except LDAPException:
            pass
