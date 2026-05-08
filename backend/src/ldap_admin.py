"""Admin-only LDAP user creation. Behind LDAP_USER_CREATION_ENABLED feature flag.

This module is a temporary bridge for local dev and the Hetzner box. It will
be retired once THL SSO is wired up.
"""
import base64
import hashlib
import os


def _make_ssha_hash(password: str) -> str:
    """Return an OpenLDAP-compatible {SSHA} hash for `password`.

    Format: '{SSHA}' + base64( sha1(password + salt) + salt ),
    salt is 4 random bytes (matches OpenLDAP defaults).
    """
    salt = os.urandom(4)
    digest = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return "{SSHA}" + base64.b64encode(digest + salt).decode("ascii")
