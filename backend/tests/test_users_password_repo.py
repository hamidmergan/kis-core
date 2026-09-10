"""Writing and reading the password column, against the real database."""

import uuid

import pytest

from src import database


@pytest.fixture
def konto():
    """A throwaway account, removed again afterwards."""
    name = f"pwtest-{uuid.uuid4().hex[:8]}"
    user_id = database.create_user(name, "Pw Test", f"{name}@example.org", 1, "user")
    yield user_id, name, f"{name}@example.org"
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()


def test_a_new_account_starts_without_a_password(konto):
    _, name, _ = konto
    assert database.get_user_by_username(name)["password_hash"] is None


def test_the_password_can_be_written_and_read_back(konto):
    user_id, name, _ = konto
    database.set_user_password(user_id, "$2b$12$abc")
    assert database.get_user_by_username(name)["password_hash"] == "$2b$12$abc"


def test_the_password_can_be_cleared(konto):
    user_id, name, _ = konto
    database.set_user_password(user_id, "$2b$12$abc")
    database.set_user_password(user_id, None)
    assert database.get_user_by_username(name)["password_hash"] is None


def test_the_account_is_found_by_its_mail_address(konto):
    user_id, _, mail = konto
    assert database.get_user_by_email(mail)["id"] == user_id


def test_the_mail_lookup_ignores_case_and_spaces(konto):
    user_id, _, mail = konto
    assert database.get_user_by_email(f"  {mail.upper()}  ")["id"] == user_id


def test_an_unknown_mail_address_finds_nothing():
    assert database.get_user_by_email("gibtsnicht@example.org") is None


def test_an_empty_mail_address_finds_nothing():
    # Accounts without a mail carry NULL, an empty search must not match them.
    assert database.get_user_by_email("") is None
    assert database.get_user_by_email("   ") is None


def test_create_user_takes_a_password_right_away():
    name = f"pwtest-{uuid.uuid4().hex[:8]}"
    user_id = database.create_user(name, "Pw Test", None, 1, "user", password_hash="$2b$12$xyz")
    try:
        assert database.get_user_by_username(name)["password_hash"] == "$2b$12$xyz"
    finally:
        with database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
