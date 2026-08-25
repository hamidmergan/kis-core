from datetime import datetime, timedelta

import pytest

from src.features.invites.service import (
    InviteValidationError,
    new_token,
    status_of,
    uid_from_email,
)


def test_uid_from_email_takes_local_part():
    assert uid_from_email("max.mustermann@th-luebeck.de") == "max.mustermann"


def test_uid_from_email_normalizes_case_and_umlauts():
    assert uid_from_email("Jörg.Müller@th-luebeck.de") == "joerg.mueller"


def test_uid_from_email_drops_characters_ldap_does_not_accept():
    assert uid_from_email("anna+test@th-luebeck.de") == "annatest"


@pytest.mark.parametrize("email", ["!@th-luebeck.de", "a@th-luebeck.de"])
def test_uid_from_email_rejects_unusable_local_part(email):
    with pytest.raises(InviteValidationError):
        uid_from_email(email)


def test_new_token_is_long_and_unique():
    erster, zweiter = new_token(), new_token()
    assert len(erster) >= 32
    assert erster != zweiter


JETZT = datetime(2026, 8, 25, 12, 0, 0)


def test_status_open_when_unused_and_not_expired():
    assert status_of(used_at=None, expires_at=JETZT + timedelta(days=1), now=JETZT) == "open"


def test_status_expired_when_valid_until_is_past():
    assert status_of(used_at=None, expires_at=JETZT - timedelta(seconds=1), now=JETZT) == "expired"


def test_status_used_wins_over_expired():
    assert status_of(
        used_at=JETZT - timedelta(days=2),
        expires_at=JETZT - timedelta(days=1),
        now=JETZT,
    ) == "used"
