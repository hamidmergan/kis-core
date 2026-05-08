# Admin: Create LDAP user via UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-panel button that creates new LDAP users in the local/Hetzner OpenLDAP container, gated by an env flag so the feature disappears after THL SSO migration.

**Architecture:** Backend service uses ldap3 to add an `inetOrgPerson` entry with an SSHA-hashed password generated server-side. Route exposes it under `/api/admin/ldap-users` behind admin guard + env flag. Frontend shows a creation dialog and reveals the generated password exactly once.

**Tech Stack:** FastAPI, pydantic v2, ldap3, hashlib (stdlib), Next.js 15 + next-intl, React 19, Phosphor Icons.

**Spec:** `docs/superpowers/specs/2026-05-08-admin-create-ldap-user-design.md`

---

## File Structure

**Create:**
- `backend/src/ldap_admin.py` — SSHA hashing, password generation, `create_ldap_user()` service
- `backend/src/routes/admin/ldap_users.py` — `POST /admin/ldap-users` route
- `backend/tests/test_ldap_admin.py` — unit tests for service helpers and validation
- `backend/tests/test_admin_ldap_users_route.py` — route-level tests with TestClient
- `frontend/src/app/[locale]/admin/_components/CreateLdapUserDialog.tsx` — modal with form + success states

**Modify:**
- `backend/src/config.py` — add `ldap_user_creation_enabled` setting
- `backend/src/permissions.py` — add `allow_ldap_user_create` field
- `backend/src/routes/auth.py` — surface `allow_ldap_user_create` in `/auth/status`
- `backend/src/routes/admin/__init__.py` — register new sub-router
- `backend/src/_i18n_fragments/admin.py` — add `admin.ldap.*` keys
- `backend/tests/test_permissions.py` — cover new permission field
- `frontend/messages/de.json` + `en.json` — `admin.createLdapUser.*` keys
- `frontend/src/app/[locale]/admin/_components/UsersTab.tsx` — add button + dialog hook
- `frontend/src/app/[locale]/admin/_shared.tsx` — extend permissions type if it lives there

---

## Task 1: SSHA hashing helper

**Files:**
- Create: `backend/src/ldap_admin.py`
- Create: `backend/tests/test_ldap_admin.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_ldap_admin.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest backend/tests/test_ldap_admin.py -v`
Expected: ImportError / ModuleNotFoundError for `src.ldap_admin._make_ssha_hash`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/ldap_admin.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest backend/tests/test_ldap_admin.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/ldap_admin.py backend/tests/test_ldap_admin.py
git commit -m "feat(ldap-admin): SSHA hash helper for OpenLDAP userPassword"
```

---

## Task 2: Password generator + input validation

**Files:**
- Modify: `backend/src/ldap_admin.py`
- Modify: `backend/tests/test_ldap_admin.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ldap_admin.py`:

```python
import pytest

from src.ldap_admin import _generate_password, validate_inputs, LdapValidationError


def test_generate_password_returns_url_safe_string():
    pw = _generate_password()
    assert isinstance(pw, str)
    assert len(pw) >= 16
    # token_urlsafe alphabet
    assert all(c.isalnum() or c in "-_" for c in pw)
    # Multiple calls return distinct values
    assert _generate_password() != pw


@pytest.mark.parametrize("uid", ["a", "ab", "valid_user.1", "u-2"])
def test_validate_inputs_accepts_valid_uid(uid):
    validate_inputs(uid=uid, given_name="A", surname="B", email="a@b.de", employee_type="staff")


@pytest.mark.parametrize("uid", ["", "A", "with space", "ümlaut", "x" * 33, "../etc"])
def test_validate_inputs_rejects_bad_uid(uid):
    with pytest.raises(LdapValidationError):
        validate_inputs(uid=uid, given_name="A", surname="B", email="a@b.de", employee_type="staff")


def test_validate_inputs_rejects_bad_email():
    with pytest.raises(LdapValidationError):
        validate_inputs(uid="ok", given_name="A", surname="B", email="not-an-email", employee_type="staff")


def test_validate_inputs_rejects_bad_employee_type():
    with pytest.raises(LdapValidationError):
        validate_inputs(uid="ok", given_name="A", surname="B", email="a@b.de", employee_type="admin")


def test_validate_inputs_rejects_blank_names():
    with pytest.raises(LdapValidationError):
        validate_inputs(uid="ok", given_name="", surname="B", email="a@b.de", employee_type="staff")
    with pytest.raises(LdapValidationError):
        validate_inputs(uid="ok", given_name="A", surname="", email="a@b.de", employee_type="staff")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest backend/tests/test_ldap_admin.py -v`
Expected: ImportError for `_generate_password`, `validate_inputs`, `LdapValidationError`.

- [ ] **Step 3: Extend implementation**

Append to `backend/src/ldap_admin.py`:

```python
import re
import secrets


_UID_RE = re.compile(r"^[a-z0-9_.-]{2,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_EMPLOYEE_TYPES = ("staff", "student")


class LdapValidationError(ValueError):
    """Raised when input does not pass uid/email/employee_type rules."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


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
```

- [ ] **Step 4: Run tests**

Run: `docker compose exec backend pytest backend/tests/test_ldap_admin.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/ldap_admin.py backend/tests/test_ldap_admin.py
git commit -m "feat(ldap-admin): password generator and input validation"
```

---

## Task 3: `create_ldap_user` service (with mocked Connection)

**Files:**
- Modify: `backend/src/ldap_admin.py`
- Modify: `backend/tests/test_ldap_admin.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ldap_admin.py`:

```python
from unittest.mock import MagicMock, patch

from src.ldap_admin import (
    LdapUserExistsError,
    LdapServiceError,
    create_ldap_user,
)


def _fake_settings(**overrides):
    base = MagicMock()
    base.ldap_server = "ldap://openldap"
    base.ldap_port = 389
    base.ldap_use_ssl = False
    base.ldap_base_dn = "dc=th-luebeck,dc=de"
    base.ldap_bind_dn = "cn=admin,dc=th-luebeck,dc=de"
    base.ldap_bind_password = "admin"
    base.ldap_attr_username = "uid"
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


@patch("src.ldap_admin.Connection")
@patch("src.ldap_admin.Server")
def test_create_ldap_user_happy_path(server_mock, conn_cls_mock):
    conn = MagicMock()
    conn.add.return_value = True
    conn.result = {"description": "success"}
    conn_cls_mock.return_value = conn

    pw = create_ldap_user(
        settings=_fake_settings(),
        uid="newuser",
        given_name="New",
        surname="User",
        email="new@th-luebeck.de",
        employee_type="staff",
    )

    assert isinstance(pw, str) and len(pw) >= 16
    conn.add.assert_called_once()
    dn, classes, attrs = conn.add.call_args.args
    assert dn == "uid=newuser,ou=people,dc=th-luebeck,dc=de"
    assert "inetOrgPerson" in classes
    assert attrs["uid"] == "newuser"
    assert attrs["cn"] == "New User"
    assert attrs["sn"] == "User"
    assert attrs["mail"] == "new@th-luebeck.de"
    assert attrs["employeeType"] == "staff"
    assert attrs["userPassword"].startswith("{SSHA}")


@patch("src.ldap_admin.Connection")
@patch("src.ldap_admin.Server")
def test_create_ldap_user_conflict_raises(server_mock, conn_cls_mock):
    conn = MagicMock()
    conn.add.return_value = False
    conn.result = {"description": "entryAlreadyExists", "result": 68}
    conn_cls_mock.return_value = conn

    with pytest.raises(LdapUserExistsError):
        create_ldap_user(
            settings=_fake_settings(),
            uid="existing",
            given_name="A",
            surname="B",
            email="a@b.de",
            employee_type="student",
        )


@patch("src.ldap_admin.Connection")
@patch("src.ldap_admin.Server")
def test_create_ldap_user_other_failure_raises_service_error(server_mock, conn_cls_mock):
    conn = MagicMock()
    conn.add.return_value = False
    conn.result = {"description": "insufficientAccessRights", "result": 50}
    conn_cls_mock.return_value = conn

    with pytest.raises(LdapServiceError):
        create_ldap_user(
            settings=_fake_settings(),
            uid="ok",
            given_name="A",
            surname="B",
            email="a@b.de",
            employee_type="staff",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest backend/tests/test_ldap_admin.py -v`
Expected: ImportError for `LdapUserExistsError`, `LdapServiceError`, `create_ldap_user`.

- [ ] **Step 3: Implement service**

Append to `backend/src/ldap_admin.py`:

```python
from ldap3 import ALL, Connection, Server
from ldap3.core.exceptions import LDAPException

from src.config import Settings


class LdapUserExistsError(Exception):
    """Raised when the uid already exists in the directory."""


class LdapServiceError(RuntimeError):
    """Raised on bind failures or unexpected LDAP add errors."""


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
        get_info=ALL,
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
```

- [ ] **Step 4: Run tests**

Run: `docker compose exec backend pytest backend/tests/test_ldap_admin.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/ldap_admin.py backend/tests/test_ldap_admin.py
git commit -m "feat(ldap-admin): create_ldap_user service with conflict handling"
```

---

## Task 4: Settings flag + permission field

**Files:**
- Modify: `backend/src/config.py:60-71`
- Modify: `backend/src/permissions.py`
- Modify: `backend/src/routes/auth.py:139-150`
- Modify: `backend/tests/test_permissions.py`

- [ ] **Step 1: Write failing test for permissions**

Append to `backend/tests/test_permissions.py`:

```python
def test_admin_has_ldap_user_create_when_flag_on(monkeypatch):
    from src.permissions import resolve_user_permissions

    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    perms = resolve_user_permissions(role="admin", custom_role_id=None, is_env_admin=False)
    assert perms.allow_ldap_user_create is True


def test_staff_does_not_get_ldap_user_create_even_with_flag(monkeypatch):
    from src.permissions import resolve_user_permissions

    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    perms = resolve_user_permissions(role="staff", custom_role_id=None, is_env_admin=False)
    assert perms.allow_ldap_user_create is False


def test_admin_no_ldap_user_create_when_flag_off(monkeypatch):
    from src.permissions import resolve_user_permissions

    monkeypatch.delenv("LDAP_USER_CREATION_ENABLED", raising=False)
    perms = resolve_user_permissions(role="admin", custom_role_id=None, is_env_admin=False)
    assert perms.allow_ldap_user_create is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest backend/tests/test_permissions.py -v`
Expected: AttributeError on `allow_ldap_user_create`.

- [ ] **Step 3: Add setting**

In `backend/src/config.py`, add inside the LDAP block (after `ldap_use_ssl: bool = False`):

```python
    # Admin-only feature flag: enables UI for creating LDAP users.
    # Disable on prod / SSO deployments.
    ldap_user_creation_enabled: bool = False
```

- [ ] **Step 4: Extend Permissions and resolver**

Replace `backend/src/permissions.py` `Permissions` dataclass and the system-role helpers:

```python
@dataclass(frozen=True)
class Permissions:
    allow_admin_panel: bool
    allow_aia: bool
    allow_workspace_create: bool
    allow_ldap_user_create: bool
    tools: tuple[str, ...]
```

Replace `permissions_for_system_role` to include the new field. The flag itself
is owned by Settings, so the resolver layers it on top:

```python
def permissions_for_system_role(role: str) -> Permissions:
    if role == "admin":
        return Permissions(
            allow_admin_panel=True,
            allow_aia=True,
            allow_workspace_create=True,
            allow_ldap_user_create=False,  # gated below by env flag
            tools=tuple(ALL_TOOL_KEYS),
        )
    if role == "staff":
        return Permissions(
            allow_admin_panel=False,
            allow_aia=True,
            allow_workspace_create=True,
            allow_ldap_user_create=False,
            tools=tuple(ALL_TOOL_KEYS),
        )
    if role == "user":
        return Permissions(
            allow_admin_panel=False,
            allow_aia=True,
            allow_workspace_create=False,
            allow_ldap_user_create=False,
            tools=(),
        )
    raise ValueError(f"Unknown system role: {role!r}")


def custom_role_permissions(allow_aia: bool, tool_keys: list[str]) -> Permissions:
    valid_tools = tuple(k for k in tool_keys if k in ALL_TOOL_KEYS)
    return Permissions(
        allow_admin_panel=False,
        allow_aia=allow_aia,
        allow_workspace_create=False,
        allow_ldap_user_create=False,
        tools=valid_tools,
    )
```

In `resolve_user_permissions`, layer the env flag onto admin results:

```python
def resolve_user_permissions(
    role: str,
    custom_role_id: int | None,
    is_env_admin: bool,
) -> Permissions:
    base = _resolve_base_permissions(role, custom_role_id, is_env_admin)
    if base.allow_admin_panel:
        from src.dependencies import get_settings
        if get_settings().ldap_user_creation_enabled:
            return Permissions(
                allow_admin_panel=base.allow_admin_panel,
                allow_aia=base.allow_aia,
                allow_workspace_create=base.allow_workspace_create,
                allow_ldap_user_create=True,
                tools=base.tools,
            )
    return base


def _resolve_base_permissions(
    role: str,
    custom_role_id: int | None,
    is_env_admin: bool,
) -> Permissions:
    if is_env_admin:
        return permissions_for_system_role("admin")
    if role in SYSTEM_ROLES:
        return permissions_for_system_role(role)
    if role == "custom" and custom_role_id is not None:
        from src import database
        cr = database.get_custom_role(custom_role_id)
        if cr is None:
            return permissions_for_system_role("user")
        return custom_role_permissions(cr["allow_aia"], cr["allowed_tools"])
    return permissions_for_system_role("user")
```

- [ ] **Step 5: Surface flag in /auth/status**

In `backend/src/routes/auth.py`, edit the `payload` block (around lines 139-150) to include the new key:

```python
    payload = {
        "authenticated": True,
        "is_admin": perms.allow_admin_panel,
        "role": data.get("role", "user"),
        "custom_role_id": data.get("custom_role_id"),
        "permissions": {
            "allow_admin_panel": perms.allow_admin_panel,
            "allow_aia": perms.allow_aia,
            "allow_workspace_create": perms.allow_workspace_create,
            "allow_ldap_user_create": perms.allow_ldap_user_create,
            "tools": list(perms.tools),
        },
    }
```

- [ ] **Step 6: Run all backend tests**

Run: `docker compose exec backend pytest backend/tests -v`
Expected: all green (test_permissions, test_rbac_dependencies, test_ldap_admin).

- [ ] **Step 7: Commit**

```bash
git add backend/src/config.py backend/src/permissions.py backend/src/routes/auth.py backend/tests/test_permissions.py
git commit -m "feat(rbac): allow_ldap_user_create permission gated by env flag"
```

---

## Task 5: Backend i18n keys

**Files:**
- Modify: `backend/src/_i18n_fragments/admin.py`

- [ ] **Step 1: Add keys to the admin fragment**

Append to the `MESSAGES` dict in `backend/src/_i18n_fragments/admin.py`:

```python
    "admin.ldap.userExists": {
        "de": "Benutzer existiert bereits",
        "en": "User already exists",
    },
    "admin.ldap.invalidUid": {
        "de": "Ungültiger Benutzername (a-z, 0-9, _ . -, 2-32 Zeichen)",
        "en": "Invalid username (a-z, 0-9, _ . -, 2-32 characters)",
    },
    "admin.ldap.invalidEmail": {
        "de": "Ungültige E-Mail-Adresse",
        "en": "Invalid email address",
    },
    "admin.ldap.invalidEmployeeType": {
        "de": "Rolle muss 'staff' oder 'student' sein",
        "en": "Role must be 'staff' or 'student'",
    },
    "admin.ldap.nameRequired": {
        "de": "Vor- und Nachname sind Pflicht",
        "en": "First and last name are required",
    },
    "admin.ldap.addFailed": {
        "de": "LDAP-Eintrag fehlgeschlagen",
        "en": "LDAP add failed",
    },
    "admin.ldap.featureDisabled": {
        "de": "LDAP-Benutzererstellung ist deaktiviert",
        "en": "LDAP user creation is disabled",
    },
```

- [ ] **Step 2: Smoke-check the keys load**

Run: `docker compose exec backend python -c "from src.i18n import t; print(t('admin.ldap.userExists', 'de'))"`
Expected output: `Benutzer existiert bereits`

- [ ] **Step 3: Commit**

```bash
git add backend/src/_i18n_fragments/admin.py
git commit -m "feat(i18n): admin.ldap.* keys for LDAP user creation"
```

---

## Task 6: Backend route `POST /admin/ldap-users`

**Files:**
- Create: `backend/src/routes/admin/ldap_users.py`
- Create: `backend/tests/test_admin_ldap_users_route.py`
- Modify: `backend/src/routes/admin/__init__.py`

- [ ] **Step 1: Write failing route tests**

```python
# backend/tests/test_admin_ldap_users_route.py
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=th-luebeck,dc=de")
    monkeypatch.setenv("LDAP_BIND_DN", "cn=admin,dc=th-luebeck,dc=de")
    monkeypatch.setenv("LDAP_BIND_PASSWORD", "admin")
    monkeypatch.setenv("LDAP_SERVER", "ldap://openldap")

    # Late import so env vars apply.
    from src.dependencies import get_admin_user, get_settings
    from src.main import app

    get_settings.cache_clear()
    app.dependency_overrides[get_admin_user] = lambda: {"user_id": 1, "email": "admin@th-luebeck.de"}
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_create_ldap_user_returns_password(client):
    with patch("src.routes.admin.ldap_users.create_ldap_user", return_value="GENERATED-pw"):
        r = client.post(
            "/api/admin/ldap-users",
            json={
                "uid": "newone",
                "given_name": "New",
                "surname": "One",
                "email": "n@th-luebeck.de",
                "employee_type": "staff",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["uid"] == "newone"
    assert body["generated_password"] == "GENERATED-pw"


def test_create_ldap_user_conflict_returns_409(client):
    from src.ldap_admin import LdapUserExistsError

    with patch(
        "src.routes.admin.ldap_users.create_ldap_user",
        side_effect=LdapUserExistsError("newone"),
    ):
        r = client.post(
            "/api/admin/ldap-users",
            json={
                "uid": "newone",
                "given_name": "N",
                "surname": "O",
                "email": "n@th-luebeck.de",
                "employee_type": "staff",
            },
        )
    assert r.status_code == 409


def test_create_ldap_user_validation_returns_400(client):
    from src.ldap_admin import LdapValidationError

    with patch(
        "src.routes.admin.ldap_users.create_ldap_user",
        side_effect=LdapValidationError("uid", "must match pattern"),
    ):
        r = client.post(
            "/api/admin/ldap-users",
            json={
                "uid": "BAD",
                "given_name": "N",
                "surname": "O",
                "email": "n@th-luebeck.de",
                "employee_type": "staff",
            },
        )
    assert r.status_code == 400


def test_create_ldap_user_404_when_flag_off(monkeypatch):
    monkeypatch.delenv("LDAP_USER_CREATION_ENABLED", raising=False)
    from src.dependencies import get_admin_user, get_settings
    from src.main import app

    get_settings.cache_clear()
    app.dependency_overrides[get_admin_user] = lambda: {"user_id": 1, "email": "admin@th-luebeck.de"}
    try:
        c = TestClient(app)
        r = c.post(
            "/api/admin/ldap-users",
            json={
                "uid": "x",
                "given_name": "A",
                "surname": "B",
                "email": "a@b.de",
                "employee_type": "staff",
            },
        )
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest backend/tests/test_admin_ldap_users_route.py -v`
Expected: 404 from FastAPI on the path (route not registered).

- [ ] **Step 3: Implement route**

```python
# backend/src/routes/admin/ldap_users.py
"""Admin endpoint to create new LDAP users (temporary — replaced by SSO)."""
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src.dependencies import get_admin_user, get_settings
from src.i18n import get_locale, t
from src.ldap_admin import (
    LdapServiceError,
    LdapUserExistsError,
    LdapValidationError,
    create_ldap_user,
)

router = APIRouter(tags=["admin: ldap-users"])


class CreateLdapUserPayload(BaseModel):
    uid: str = Field(..., min_length=2, max_length=32)
    given_name: str = Field(..., min_length=1, max_length=64)
    surname: str = Field(..., min_length=1, max_length=64)
    email: str = Field(..., min_length=3, max_length=128)
    employee_type: str = Field(..., pattern="^(staff|student)$")


@router.post("/ldap-users")
async def admin_create_ldap_user(
    payload: CreateLdapUserPayload,
    admin: dict = Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    settings = get_settings()
    if not settings.ldap_user_creation_enabled:
        raise HTTPException(status_code=404, detail=t("admin.ldap.featureDisabled", locale))

    try:
        password = create_ldap_user(
            settings=settings,
            uid=payload.uid,
            given_name=payload.given_name,
            surname=payload.surname,
            email=payload.email,
            employee_type=payload.employee_type,
        )
    except LdapValidationError as e:
        key = {
            "uid": "admin.ldap.invalidUid",
            "email": "admin.ldap.invalidEmail",
            "employee_type": "admin.ldap.invalidEmployeeType",
            "given_name": "admin.ldap.nameRequired",
            "surname": "admin.ldap.nameRequired",
        }.get(e.field, "admin.ldap.addFailed")
        raise HTTPException(status_code=400, detail=t(key, locale))
    except LdapUserExistsError:
        raise HTTPException(status_code=409, detail=t("admin.ldap.userExists", locale))
    except LdapServiceError as e:
        logger.error("LDAP add failed for uid={}: {}", payload.uid, e)
        raise HTTPException(status_code=500, detail=t("admin.ldap.addFailed", locale))

    logger.info("admin {} created LDAP user uid={}", admin.get("email"), payload.uid)
    return {"uid": payload.uid, "generated_password": password}
```

- [ ] **Step 4: Register sub-router**

In `backend/src/routes/admin/__init__.py`, add the import and include:

```python
from src.routes.admin.ldap_users import router as _ldap_users_router
# ... existing includes ...
router.include_router(_ldap_users_router)
```

- [ ] **Step 5: Run tests**

Run: `docker compose exec backend pytest backend/tests/test_admin_ldap_users_route.py -v`
Expected: all 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/src/routes/admin/ldap_users.py backend/src/routes/admin/__init__.py backend/tests/test_admin_ldap_users_route.py
git commit -m "feat(admin-api): POST /admin/ldap-users endpoint behind feature flag"
```

---

## Task 7: Frontend i18n keys

**Files:**
- Modify: `frontend/messages/de.json`
- Modify: `frontend/messages/en.json`

- [ ] **Step 1: Locate the `admin.users.*` block in `de.json`**

Run: `grep -n '"users"' frontend/messages/de.json | head`
Expected: shows the line number for the `admin.users` object (around line 681 today).

- [ ] **Step 2: Add `admin.createLdapUser.*` block to `de.json`**

Insert immediately AFTER the closing `}` of the `admin.users` block, inside the `admin` object:

```json
    "createLdapUser": {
      "buttonLabel": "+ Benutzer anlegen",
      "title": "LDAP-Benutzer anlegen",
      "fieldUid": "Benutzername (uid)",
      "fieldUidHint": "Kleinbuchstaben, Zahlen, _ . -, 2-32 Zeichen",
      "fieldGivenName": "Vorname",
      "fieldSurname": "Nachname",
      "fieldEmail": "E-Mail",
      "fieldEmployeeType": "Rolle",
      "employeeTypeStaff": "Mitarbeitend (staff)",
      "employeeTypeStudent": "Studierende:r (student)",
      "submit": "Anlegen",
      "cancel": "Abbrechen",
      "successTitle": "Benutzer angelegt",
      "successPasswordLabel": "Initial-Passwort",
      "successCopyButton": "Kopieren",
      "successCopied": "Kopiert!",
      "successWarning": "Dieses Passwort wird NUR JETZT angezeigt. Notiere oder kopiere es, bevor du den Dialog schließt.",
      "successClose": "Schließen",
      "errorGeneric": "Anlegen fehlgeschlagen"
    },
```

- [ ] **Step 3: Mirror in `en.json`**

Insert at the same logical position in `frontend/messages/en.json`:

```json
    "createLdapUser": {
      "buttonLabel": "+ Add user",
      "title": "Create LDAP user",
      "fieldUid": "Username (uid)",
      "fieldUidHint": "Lowercase, digits, _ . -, 2-32 characters",
      "fieldGivenName": "First name",
      "fieldSurname": "Last name",
      "fieldEmail": "Email",
      "fieldEmployeeType": "Role",
      "employeeTypeStaff": "Staff",
      "employeeTypeStudent": "Student",
      "submit": "Create",
      "cancel": "Cancel",
      "successTitle": "User created",
      "successPasswordLabel": "Initial password",
      "successCopyButton": "Copy",
      "successCopied": "Copied!",
      "successWarning": "This password is shown ONCE. Copy or write it down before closing the dialog.",
      "successClose": "Close",
      "errorGeneric": "Creation failed"
    },
```

- [ ] **Step 4: Verify i18n parity**

Run: `cd frontend && npm run check:i18n`
Expected: no key drift between locales.

- [ ] **Step 5: Commit**

```bash
git add frontend/messages/de.json frontend/messages/en.json
git commit -m "feat(i18n): admin.createLdapUser keys (DE+EN)"
```

---

## Task 8: Frontend `CreateLdapUserDialog` component

**Files:**
- Create: `frontend/src/app/[locale]/admin/_components/CreateLdapUserDialog.tsx`

- [ ] **Step 1: Implement the component**

```tsx
"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Copy, Check, Warning } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";

type EmployeeType = "staff" | "student";

type Props = {
  onClose: () => void;
};

type FormState = {
  uid: string;
  given_name: string;
  surname: string;
  email: string;
  employee_type: EmployeeType;
};

const EMPTY: FormState = {
  uid: "",
  given_name: "",
  surname: "",
  email: "",
  employee_type: "staff",
};

export default function CreateLdapUserDialog({ onClose }: Props) {
  const t = useTranslations("admin.createLdapUser");
  const [form, setForm] = useState<FormState>(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ uid: string; password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const employeeTypeOptions = [
    { value: "staff", label: t("employeeTypeStaff") },
    { value: "student", label: t("employeeTypeStudent") },
  ];

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch("/api/admin/ldap-users", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (r.ok) {
        const body = await r.json();
        setSuccess({ uid: body.uid, password: body.generated_password });
      } else {
        const body = await r.json().catch(() => ({}));
        setError(body.detail || t("errorGeneric"));
      }
    } catch {
      setError(t("errorGeneric"));
    } finally {
      setSubmitting(false);
    }
  }

  async function copyPassword() {
    if (!success) return;
    await navigator.clipboard.writeText(success.password);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-background border border-border rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        {success ? (
          <>
            <h2 className="text-lg font-semibold">{t("successTitle")}</h2>
            <p className="text-sm text-muted-soft">uid: <span className="font-mono">{success.uid}</span></p>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("successPasswordLabel")}</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 font-mono text-sm bg-surface border border-border rounded-md px-3 py-2 select-all">
                  {success.password}
                </code>
                <button
                  type="button"
                  onClick={copyPassword}
                  className="px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1"
                >
                  {copied ? <Check size={16} weight="bold" /> : <Copy size={16} weight="bold" />}
                  {copied ? t("successCopied") : t("successCopyButton")}
                </button>
              </div>
            </div>

            <div className="flex items-start gap-2 bg-warning-bg text-warning-strong text-sm rounded-md px-3 py-2">
              <Warning size={18} weight="bold" className="mt-0.5 shrink-0" />
              <span>{t("successWarning")}</span>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm bg-kb text-white rounded-md"
              >
                {t("successClose")}
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <h2 className="text-lg font-semibold">{t("title")}</h2>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("fieldUid")}</label>
              <input
                type="text"
                required
                value={form.uid}
                onChange={(e) => update("uid", e.target.value.toLowerCase())}
                pattern="[a-z0-9_.-]{2,32}"
                className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb font-mono"
              />
              <p className="text-xs text-muted-soft">{t("fieldUidHint")}</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wide text-muted">{t("fieldGivenName")}</label>
                <input
                  type="text"
                  required
                  value={form.given_name}
                  onChange={(e) => update("given_name", e.target.value)}
                  className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wide text-muted">{t("fieldSurname")}</label>
                <input
                  type="text"
                  required
                  value={form.surname}
                  onChange={(e) => update("surname", e.target.value)}
                  className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("fieldEmail")}</label>
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("fieldEmployeeType")}</label>
              <Select
                value={form.employee_type}
                onChange={(v) => update("employee_type", v as EmployeeType)}
                options={employeeTypeOptions}
                className="w-full"
              />
            </div>

            {error && (
              <p className="text-sm text-error">{error}</p>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="px-4 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
              >
                {t("cancel")}
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 text-sm bg-kb text-white rounded-md disabled:opacity-60"
              >
                {t("submit")}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the file type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors related to `CreateLdapUserDialog`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/[locale]/admin/_components/CreateLdapUserDialog.tsx
git commit -m "feat(admin-ui): CreateLdapUserDialog with one-time password reveal"
```

---

## Task 9: Wire dialog into `UsersTab`

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/UsersTab.tsx`

- [ ] **Step 1: Add state + permission read**

At the top of `UsersTab`, alongside the other `useState` calls (around line 24), add:

```tsx
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [allowLdapCreate, setAllowLdapCreate] = useState(false);
```

- [ ] **Step 2: Read the permission from `/auth/status`**

Replace the existing `auth/status` fetch (lines 78-80) with:

```tsx
    fetch("/auth/status", { credentials: "include" })
      .then((r) => r.ok ? r.json() : null)
      .then((s) => {
        if (s?.email) setAdminEmail(String(s.email).toLowerCase());
        setAllowLdapCreate(Boolean(s?.permissions?.allow_ldap_user_create));
      });
```

- [ ] **Step 3: Add the import**

At the top of the file, alongside the other imports:

```tsx
import CreateLdapUserDialog from "./CreateLdapUserDialog";
```

- [ ] **Step 4: Render the button + dialog**

In the header `<div className="flex flex-wrap gap-2 items-center">` (line 108), append a button BEFORE the closing `</div>`:

```tsx
        {allowLdapCreate && (
          <button
            type="button"
            onClick={() => setShowCreateDialog(true)}
            className="px-3 py-2 text-sm bg-kb text-white rounded-md whitespace-nowrap"
          >
            {t("createLdapUser.buttonLabel")}
          </button>
        )}
```

At the very bottom of the returned JSX (after the pagination block, before the outer `</div>`), add:

```tsx
      {showCreateDialog && (
        <CreateLdapUserDialog onClose={() => {
          setShowCreateDialog(false);
          // Refresh list — new user appears in DB only after first login,
          // but we still re-trigger the existing fetch so any concurrent change shows.
          setOffset((o) => o);
        }} />
      )}
```

- [ ] **Step 5: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Smoke-test in browser**

In a separate terminal: `start-local.bat` (or whatever the user normally has running). With the dev frontend on port 3000 already up:

1. Open `http://localhost:3000/de/admin?tab=users` while logged in as admin.
2. Confirm the "+ Benutzer anlegen" button is visible (only if `LDAP_USER_CREATION_ENABLED=true` in backend `.env`).
3. Click → fill form → submit.
4. Verify the success view shows the password in monospace, "Kopieren" copies it, the warning is visible, and "Schließen" closes the dialog.
5. Log out, log in as the new uid with the shown password — must succeed (existing login flow creates the DB row and assigns role from `employeeType`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/[locale]/admin/_components/UsersTab.tsx
git commit -m "feat(admin-ui): wire CreateLdapUserDialog into UsersTab header"
```

---

## Task 10: Final verification

- [ ] **Step 1: Backend test suite**

Run: `docker compose exec backend pytest backend/tests -v`
Expected: all green.

- [ ] **Step 2: i18n parity**

Run: `cd frontend && npm run check:i18n`
Expected: no drift.

- [ ] **Step 3: Type check + build sanity**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 4: End-to-end smoke**

With the local stack running and `LDAP_USER_CREATION_ENABLED=true` in `.env`:

1. Login as admin → admin/users → click "+ Benutzer anlegen".
2. Create a `staff` user (e.g. uid `t1`).
3. Copy password, close dialog.
4. Logout. Login as `t1` with the copied password.
5. Confirm new row appears in `users` table with `role=staff`.
6. Toggle `LDAP_USER_CREATION_ENABLED=false`, restart backend, reload admin → button is gone, `POST /api/admin/ldap-users` returns 404.

- [ ] **Step 5: Final commit only if cleanup needed**

If any test or verification revealed an issue and you fixed it, create a final commit. Otherwise no-op.

---

## Out of scope (do NOT implement)

- Editing existing LDAP users
- Deleting LDAP users
- Resetting passwords
- Listing the LDAP directory in the admin UI
- Email delivery of generated passwords
- Any DB migration (the user appears in the KIS DB on first login, via the existing `routes/auth.py` flow)
