"""The database side of the access codes: written, committed, correctly conditioned."""

from datetime import datetime

import pytest

from src.features.access_codes import repository as repo

ABLAUF = datetime(2026, 9, 30, 12, 0, 0)


class _FakeCursor:
    def __init__(self, rows, calls):
        self._rows = list(rows)
        self._calls = calls
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append(("execute", " ".join(sql.split()), params))
        self.rowcount = 1

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, rows, calls):
        self._rows = rows
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._rows, self._calls)

    def commit(self):
        self._calls.append(("commit", None, None))


@pytest.fixture
def fake_db(monkeypatch):
    def _apply(rows=()):
        calls: list[tuple] = []
        monkeypatch.setattr(repo, "get_connection", lambda: _FakeConn(rows, calls))
        return calls
    return _apply


def test_creating_a_code_commits(fake_db):
    calls = fake_db(rows=[(7,)])

    neu = repo.create_code(
        code="KIS-4K2P-7RXM",
        label="Kollegen August",
        role="staff",
        custom_role_id=None,
        max_uses=50,
        valid_until=ABLAUF,
        access_days=14,
        created_by=1,
    )

    assert neu == 7
    assert ("commit", None, None) in calls, "ohne commit sieht der naechste Aufruf nichts"


def test_claim_use_only_counts_up_while_the_code_has_room(fake_db):
    calls = fake_db(rows=[(7,)])

    assert repo.claim_use(7) is True

    anweisungen = [c[1] for c in calls if c[0] == "execute"]
    assert any("used_count < max_uses" in a for a in anweisungen), "sonst platzt die Obergrenze"
    assert any("valid_until > NOW()" in a for a in anweisungen)
    assert any("active" in a for a in anweisungen)
    assert ("commit", None, None) in calls


def test_claim_use_reports_failure_when_nothing_changed(fake_db):
    fake_db(rows=[])
    assert repo.claim_use(7) is False


def test_release_use_never_goes_below_zero(fake_db):
    calls = fake_db()

    repo.release_use(7)

    anweisungen = [c[1] for c in calls if c[0] == "execute"]
    assert any("used_count = used_count - 1" in a for a in anweisungen)
    assert any("used_count > 0" in a for a in anweisungen)


def test_deleting_a_code_never_touches_the_users_table(fake_db):
    calls = fake_db(rows=[(7,)])

    assert repo.delete_code(7) is True

    anweisungen = [c[1] for c in calls if c[0] == "execute"]
    assert any("DELETE FROM access_codes" in a for a in anweisungen)
    assert not any("users" in a for a in anweisungen), "Loeschen darf nie ein Konto anfassen"


def test_set_user_access_writes_both_columns(fake_db):
    calls = fake_db()
    frist = datetime(2026, 9, 11, 12, 0, 0)

    repo.set_user_access(42, expires_at=frist, code_id=7)

    befehl = [c for c in calls if c[0] == "execute"][0]
    assert "access_expires_at" in befehl[1] and "access_code_id" in befehl[1]
    assert befehl[2] == (frist, 7, 42)
