import base64
import hashlib

from src.ldap_admin import _make_ssha_hash


def test_ssha_hash_has_prefix_and_verifies():
    password = "correct horse battery staple"
    digest = _make_ssha_hash(password)
    assert digest.startswith("{SSHA}")

    decoded = base64.b64decode(digest[len("{SSHA}"):])
    sha_bytes, salt = decoded[:20], decoded[20:]
    assert len(salt) == 4
    expected = hashlib.sha1(password.encode("utf-8") + salt).digest()
    assert sha_bytes == expected


def test_ssha_hash_is_salted_unique():
    a = _make_ssha_hash("same-password")
    b = _make_ssha_hash("same-password")
    assert a != b  # random salt
