"""AES-GCM wrap/unwrap for sensitive fields in admin config exports.

The export key lives in env as ``KIS_EXPORT_KEY`` and is shared across all
exports from the same deployment. It is hashed (SHA-256) to derive a 32-byte
AES key, so the env value can be any non-empty string.

Envelope format (JSON-safe, embedded inline in the export):

    {"alg": "aesgcm-v1", "nonce": "<b64url-12>", "ct": "<b64url-ciphertext>"}

A missing or empty ``KIS_EXPORT_KEY`` disables wrapping — plain exports
behave like before (no api_key field included).
"""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ENVELOPE_ALG = "aesgcm-v1"


def _secret() -> str | None:
    raw = (os.environ.get("KIS_EXPORT_KEY") or "").strip()
    return raw or None


def is_export_key_configured() -> bool:
    return _secret() is not None


def _derive_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def wrap_api_key(plain: str) -> dict[str, str]:
    """Encrypt ``plain`` with the configured export key. Caller must ensure
    ``is_export_key_configured()`` is true."""
    secret = _secret()
    if secret is None:
        raise RuntimeError("KIS_EXPORT_KEY not configured")
    key = _derive_key(secret)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plain.encode("utf-8"), None)
    return {"alg": ENVELOPE_ALG, "nonce": _b64e(nonce), "ct": _b64e(ct)}


def is_envelope(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("alg") == ENVELOPE_ALG
        and isinstance(value.get("nonce"), str)
        and isinstance(value.get("ct"), str)
    )


def try_unwrap_api_key(envelope: dict[str, Any]) -> str | None:
    """Decrypt an envelope. Returns the plain key on success, ``None`` if the
    current ``KIS_EXPORT_KEY`` cannot decrypt it (wrong key, missing env,
    tampered ciphertext)."""
    secret = _secret()
    if secret is None:
        return None
    try:
        key = _derive_key(secret)
        nonce = _b64d(envelope["nonce"])
        ct = _b64d(envelope["ct"])
        pt = AESGCM(key).decrypt(nonce, ct, None)
        return pt.decode("utf-8")
    except Exception:
        return None
