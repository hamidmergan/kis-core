from datetime import datetime, timedelta

from src.features.access_codes.service import (
    demo_email,
    new_code,
    new_username,
    normalize_code,
    status_of,
)

JETZT = datetime(2026, 8, 28, 12, 0, 0)
SPAETER = JETZT + timedelta(days=1)
FRUEHER = JETZT - timedelta(seconds=1)


def test_new_code_has_the_readable_shape():
    teile = new_code().split("-")
    assert len(teile) == 2
    assert all(len(teil) == 4 for teil in teile)


def test_new_code_avoids_characters_that_look_alike():
    zusammen = "".join(new_code().replace("-", "") for _ in range(50))
    for zeichen in "01OIL":
        assert zeichen not in zusammen


def test_new_code_is_not_the_same_twice():
    assert new_code() != new_code()


def test_new_username_has_the_right_shape():
    name = new_username()
    assert len(name) == 8
    assert name == name.lower()
    assert name.isalnum()


def test_new_username_avoids_characters_that_look_alike():
    zusammen = "".join(new_username() for _ in range(50))
    for zeichen in "01oil":
        assert zeichen not in zusammen


def test_new_username_is_not_the_same_twice():
    assert new_username() != new_username()


def test_normalize_code_repairs_sloppy_typing():
    assert normalize_code(" 4k2p-7rxm ") == "4K2P-7RXM"


def test_demo_email_hangs_the_fixed_domain_on_the_user_name():
    assert demo_email("max.mustermann") == "max.mustermann@demo.kis.local"


def test_status_active_when_everything_is_fine():
    assert status_of(
        active=True, used_count=0, max_uses=50, valid_until=SPAETER, now=JETZT
    ) == "active"


def test_status_disabled_beats_everything_else():
    assert status_of(
        active=False, used_count=0, max_uses=50, valid_until=SPAETER, now=JETZT
    ) == "disabled"


def test_status_expired_when_the_deadline_is_past():
    assert status_of(
        active=True, used_count=0, max_uses=50, valid_until=FRUEHER, now=JETZT
    ) == "expired"


def test_status_full_when_every_seat_is_taken():
    assert status_of(
        active=True, used_count=50, max_uses=50, valid_until=SPAETER, now=JETZT
    ) == "full"
