# Role-Based Access Control (RBAC) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ad-hoc admin/lecturer/student role strings with a proper RBAC system that supports three fixed system roles (`admin`/`staff`/`user`) plus admin-defined custom roles, enforced on both backend and frontend.

**Architecture:**
- Three system roles (hardcoded permissions, non-editable, non-deletable): `admin` (everything incl. admin panel), `staff` (everything minus admin panel), `user` (only access to assigned workspaces, no tools, no workspace creation).
- Optional custom roles (DB-backed) with admin-configurable per-tool checkboxes + AIA-yes/no checkbox. A user has exactly ONE role: either a system role or a custom role.
- Env-admin (`ADMIN_EMAIL`) is bootstrap super-admin: always treated as `admin`, cannot be demoted/deleted.
- Backend permission enforcement via FastAPI dependencies; frontend disables UI cosmetically.
- Tool registry lives in `backend/src/tools_registry.py` (single source of truth), exposed via API for the role-builder UI; frontend `ToolsSidebar` already lists tools and stays unchanged for now.

**Tech Stack:** FastAPI + psycopg2 (raw SQL migrations in `schema.py`), Redis sessions, Next.js 15 / next-intl, Tailwind, Phosphor icons.

---

## File Structure

**Backend - new files:**
- `backend/src/tools_registry.py` - canonical list of global tool keys
- `backend/src/permissions.py` - permission constants, system role permissions, helper to compute permissions for a user
- `backend/src/dependencies_rbac.py` - new FastAPI dependencies: `require_admin`, `require_staff_or_admin`, `require_tool_access`, `require_aia_access`
- `backend/src/routes/admin/roles.py` - CRUD for custom roles
- `backend/src/database_roles.py` - DB helpers for custom roles + user role assignment
- `backend/tests/test_permissions.py` - permission logic tests
- `backend/tests/test_admin_roles_api.py` - role CRUD endpoint tests

**Backend - modified files:**
- `backend/src/core/db/schema.py` - add `custom_roles` table, migrate existing `users.role` values
- `backend/src/dependencies.py` - update `is_admin_user`/`get_admin_user` to honor new `admin` role + env-admin
- `backend/src/routes/auth.py` - normalise role on login, include permissions in session/status payload
- `backend/src/routes/admin/__init__.py` (or wherever admin router is mounted) - register new roles router
- `backend/src/routes/admin/users.py` - add endpoint to update a user's role
- All tool routes (`backend/src/routes/translate.py`, `tts.py`, `stt.py`, `image.py`, `summarize.py`, `screencast*.py`, `glossary.py`, `upload.py`) - add `require_tool_access` dependency
- AIA routes (`backend/src/routes/ai_assistant*.py`) - add `require_aia_access` dependency

**Frontend - new files:**
- `frontend/src/lib/permissions.ts` - permission constants + helpers (mirrors backend)
- `frontend/src/hooks/usePermissions.ts` - React hook returning current user's permissions + role kind
- `frontend/src/components/auth/LockedNotice.tsx` - shared "locked" indicator (icon + text)
- `frontend/src/app/[locale]/admin/_components/RolesTab.tsx` - new admin tab for custom-role CRUD
- `frontend/src/app/[locale]/admin/_components/RoleBuilderDialog.tsx` - create/edit custom role form

**Frontend - modified files:**
- `frontend/src/types/index.ts` - extend `AuthStatus` with `permissions` + `role_kind`
- `frontend/src/components/auth/ProtectedRoute.tsx` - replace string-role checks with permission checks
- `frontend/src/app/[locale]/admin/page.tsx` - register new "Rollen" tab
- `frontend/src/app/[locale]/admin/_components/UsersTab.tsx` - add role dropdown per user
- `frontend/src/app/[locale]/workspace/_components/LecturerView.tsx` (and StudentView if relevant) - disable workspace creation for `user` role + add `LockedNotice` if AIA blocked
- `frontend/src/components/layout/ToolsSidebar.tsx` - filter by `usePermissions().tools`
- `frontend/messages/de.json`, `frontend/messages/en.json` - new keys
- `backend/src/i18n.py` (and `_i18n_fragments/admin.py`) - new admin/role/permission keys

---

## Task 1: Tool Registry (Backend) + Permission Constants

**Files:**
- Create: `backend/src/tools_registry.py`
- Create: `backend/src/permissions.py`
- Test: `backend/tests/test_permissions.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_permissions.py
from src.permissions import (
    SYSTEM_ROLES,
    ALL_TOOL_KEYS,
    permissions_for_system_role,
)


def test_system_roles_constant_lists_three_fixed_roles():
    assert SYSTEM_ROLES == ("admin", "staff", "user")


def test_admin_has_all_permissions():
    perms = permissions_for_system_role("admin")
    assert perms.allow_admin_panel is True
    assert perms.allow_aia is True
    assert set(perms.tools) == set(ALL_TOOL_KEYS)


def test_staff_has_everything_except_admin_panel():
    perms = permissions_for_system_role("staff")
    assert perms.allow_admin_panel is False
    assert perms.allow_aia is True
    assert set(perms.tools) == set(ALL_TOOL_KEYS)


def test_user_has_only_aia_workspace_access_no_create():
    perms = permissions_for_system_role("user")
    assert perms.allow_admin_panel is False
    assert perms.allow_aia is True   # can OPEN assigned workspaces
    assert perms.allow_workspace_create is False
    assert perms.tools == ()


def test_unknown_role_raises():
    import pytest
    with pytest.raises(ValueError):
        permissions_for_system_role("ninja")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest backend/tests/test_permissions.py -v`
Expected: ImportError (modules don't exist yet)

- [ ] **Step 3: Implement `tools_registry.py`**

```python
# backend/src/tools_registry.py
"""Canonical registry of global tool keys.

Mirrors the frontend ToolsSidebar TOOLS array. When adding a new global tool,
update both lists.
"""

ALL_TOOL_KEYS: tuple[str, ...] = (
    "translation",
    "tts",
    "transcription",
    "image",
    "summary",
    "screencast",
    "glossary",
)
```

- [ ] **Step 4: Implement `permissions.py`**

```python
# backend/src/permissions.py
"""Permission model for RBAC.

System roles (admin/staff/user) have HARDCODED permissions defined here.
Custom roles store their permissions in the `custom_roles` DB table.
"""
from dataclasses import dataclass, field

from src.tools_registry import ALL_TOOL_KEYS

SYSTEM_ROLES: tuple[str, ...] = ("admin", "staff", "user")


@dataclass(frozen=True)
class Permissions:
    allow_admin_panel: bool
    allow_aia: bool                 # may open AIA workspaces assigned to them
    allow_workspace_create: bool    # may create new AIA workspaces
    tools: tuple[str, ...]          # tool keys the user may use


def permissions_for_system_role(role: str) -> Permissions:
    if role == "admin":
        return Permissions(
            allow_admin_panel=True,
            allow_aia=True,
            allow_workspace_create=True,
            tools=tuple(ALL_TOOL_KEYS),
        )
    if role == "staff":
        return Permissions(
            allow_admin_panel=False,
            allow_aia=True,
            allow_workspace_create=True,
            tools=tuple(ALL_TOOL_KEYS),
        )
    if role == "user":
        return Permissions(
            allow_admin_panel=False,
            allow_aia=True,                # can OPEN assigned workspaces
            allow_workspace_create=False,  # but not create
            tools=(),
        )
    raise ValueError(f"Unknown system role: {role!r}")


def custom_role_permissions(allow_aia: bool, tool_keys: list[str]) -> Permissions:
    """Permissions for a DB-backed custom role.

    Custom roles never grant admin or workspace-create rights.
    """
    valid_tools = tuple(k for k in tool_keys if k in ALL_TOOL_KEYS)
    return Permissions(
        allow_admin_panel=False,
        allow_aia=allow_aia,
        allow_workspace_create=False,
        tools=valid_tools,
    )
```

- [ ] **Step 5: Run tests to verify pass**

Run: `docker compose exec backend pytest backend/tests/test_permissions.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/src/tools_registry.py backend/src/permissions.py backend/tests/test_permissions.py
git commit -m "feat(rbac): add tool registry and system-role permission model"
```

---

## Task 2: DB Migration - Custom Roles Table + Users Role Migration

**Files:**
- Modify: `backend/src/core/db/schema.py:155-176`

- [ ] **Step 1: Add `custom_roles` table + role-value migration**

Locate the users-table block in `schema.py` (around line 155-176). Immediately AFTER the existing `ALTER TABLE users ADD COLUMN ...` lines (after line 176, before the `whitelist` table at line 177), insert:

```python
            # === Role system migration ===
            # System roles: 'admin', 'staff', 'user' (fixed, code-defined permissions).
            # Custom roles live in the custom_roles table; users.custom_role_id is set
            # iff users.role = 'custom'. Existing legacy values are migrated:
            #   'lecturer' -> 'staff'
            #   'student'  -> 'user'
            cur.execute("""
                CREATE TABLE IF NOT EXISTS custom_roles (
                    id            SERIAL PRIMARY KEY,
                    name          TEXT NOT NULL UNIQUE,
                    allow_aia     BOOLEAN NOT NULL DEFAULT FALSE,
                    allowed_tools JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_role_id INTEGER "
                "REFERENCES custom_roles(id) ON DELETE SET NULL"
            )
            # Migrate legacy role strings (idempotent).
            cur.execute("UPDATE users SET role = 'staff' WHERE role = 'lecturer'")
            cur.execute("UPDATE users SET role = 'user'  WHERE role = 'student'")
            # New default for the column going forward.
            cur.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'user'")
            # Constraint: role must be one of the four allowed values.
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'users_role_check'
                    ) THEN
                        ALTER TABLE users
                            ADD CONSTRAINT users_role_check
                            CHECK (role IN ('admin', 'staff', 'user', 'custom'));
                    END IF;
                END
                $$
            """)
```

- [ ] **Step 2: Restart backend container to apply migration**

Run (PowerShell): `docker compose restart backend`

- [ ] **Step 3: Verify schema and existing rows**

Run:
```powershell
docker compose exec postgres psql -U postgres -d kis -c "\d users"
docker compose exec postgres psql -U postgres -d kis -c "SELECT id, ldap_username, role, custom_role_id FROM users ORDER BY id"
```
Expected: `custom_role_id` column present, `role` constrained to admin/staff/user/custom, all rows have role in {staff, user, admin}.

- [ ] **Step 4: Commit**

```bash
git add backend/src/core/db/schema.py
git commit -m "feat(rbac): add custom_roles table, migrate legacy role values"
```

---

## Task 3: DB Helpers for Roles

**Files:**
- Create: `backend/src/database_roles.py`

- [ ] **Step 1: Implement role helpers**

```python
# backend/src/database_roles.py
"""DB helpers for the role system: custom-role CRUD + user-role mutation."""
from typing import Any

from src import database  # for shared connection helper


def list_custom_roles() -> list[dict[str, Any]]:
    with database.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, allow_aia, allowed_tools, created_at, updated_at "
            "FROM custom_roles ORDER BY name"
        )
        return [
            {
                "id": r[0], "name": r[1], "allow_aia": r[2],
                "allowed_tools": r[3] or [], "created_at": r[4], "updated_at": r[5],
            }
            for r in cur.fetchall()
        ]


def get_custom_role(role_id: int) -> dict[str, Any] | None:
    with database.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, allow_aia, allowed_tools FROM custom_roles WHERE id = %s",
            (role_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "name": row[1], "allow_aia": row[2], "allowed_tools": row[3] or []}


def create_custom_role(name: str, allow_aia: bool, allowed_tools: list[str]) -> int:
    with database.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO custom_roles (name, allow_aia, allowed_tools) "
            "VALUES (%s, %s, %s::jsonb) RETURNING id",
            (name, allow_aia, _json(allowed_tools)),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id


def update_custom_role(role_id: int, name: str, allow_aia: bool, allowed_tools: list[str]) -> None:
    with database.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE custom_roles SET name = %s, allow_aia = %s, allowed_tools = %s::jsonb, "
            "updated_at = NOW() WHERE id = %s",
            (name, allow_aia, _json(allowed_tools), role_id),
        )
        conn.commit()


def delete_custom_role(role_id: int) -> None:
    """Delete a custom role. Users assigned to it are automatically reset to 'user'
    via the FK ON DELETE SET NULL + an explicit role downgrade here."""
    with database.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET role = 'user', custom_role_id = NULL "
            "WHERE custom_role_id = %s",
            (role_id,),
        )
        cur.execute("DELETE FROM custom_roles WHERE id = %s", (role_id,))
        conn.commit()


def set_user_role(user_id: int, role: str, custom_role_id: int | None) -> None:
    """Set a user's role.
    - role must be one of 'admin', 'staff', 'user', 'custom'
    - if role == 'custom', custom_role_id must point to an existing custom role
    - otherwise custom_role_id must be None
    """
    if role not in ("admin", "staff", "user", "custom"):
        raise ValueError(f"Invalid role: {role!r}")
    if role == "custom":
        if custom_role_id is None or get_custom_role(custom_role_id) is None:
            raise ValueError("custom role requires existing custom_role_id")
    else:
        custom_role_id = None
    with database.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET role = %s, custom_role_id = %s WHERE id = %s",
            (role, custom_role_id, user_id),
        )
        conn.commit()


def get_user_role(user_id: int) -> tuple[str, int | None]:
    with database.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT role, custom_role_id FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"User {user_id} not found")
        return row[0], row[1]


def _json(value):
    import json
    return json.dumps(value)
```

- [ ] **Step 2: Verify imports succeed**

Run: `docker compose exec backend python -c "from src.database_roles import list_custom_roles, set_user_role; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/database_roles.py
git commit -m "feat(rbac): add custom-role and user-role DB helpers"
```

---

## Task 4: Permission Resolver + FastAPI Dependencies

**Files:**
- Create: `backend/src/dependencies_rbac.py`
- Modify: `backend/src/permissions.py` - add `resolve_user_permissions`
- Test: `backend/tests/test_permissions.py` - extend
- Test: `backend/tests/test_rbac_dependencies.py`

- [ ] **Step 1: Add `resolve_user_permissions` to `permissions.py`**

Append to `backend/src/permissions.py`:

```python
def resolve_user_permissions(
    role: str,
    custom_role_id: int | None,
    is_env_admin: bool,
) -> Permissions:
    """Compute effective permissions for a session.

    env-admin always wins (bootstrap super-admin). Otherwise: system role
    constants, or DB-backed custom role.
    """
    if is_env_admin:
        return permissions_for_system_role("admin")
    if role in SYSTEM_ROLES:
        return permissions_for_system_role(role)
    if role == "custom" and custom_role_id is not None:
        from src.database_roles import get_custom_role
        cr = get_custom_role(custom_role_id)
        if cr is None:
            # Custom role was deleted concurrently; degrade gracefully to 'user'.
            return permissions_for_system_role("user")
        return custom_role_permissions(cr["allow_aia"], cr["allowed_tools"])
    # Unknown / corrupt role -> safest fallback
    return permissions_for_system_role("user")
```

- [ ] **Step 2: Implement RBAC dependencies**

```python
# backend/src/dependencies_rbac.py
"""FastAPI dependencies enforcing RBAC. Use these to gate routes."""
from fastapi import Depends, HTTPException, Request

from src.dependencies import get_current_user, get_settings
from src.i18n import get_locale, t
from src.permissions import Permissions, resolve_user_permissions


def _is_env_admin(email: str | None) -> bool:
    settings = get_settings()
    return bool(email and settings.admin_email and email.lower() == settings.admin_email.lower())


async def get_user_permissions(request: Request) -> Permissions:
    user = await get_current_user(request)
    role = user.get("role", "user")
    custom_role_id = user.get("custom_role_id")
    is_env_admin = _is_env_admin(user.get("email"))
    return resolve_user_permissions(role, custom_role_id, is_env_admin)


async def require_admin(
    perms: Permissions = Depends(get_user_permissions),
    locale: str = Depends(get_locale),
) -> Permissions:
    if not perms.allow_admin_panel:
        raise HTTPException(status_code=403, detail=t("auth.adminRequired", locale))
    return perms


async def require_aia_access(
    perms: Permissions = Depends(get_user_permissions),
    locale: str = Depends(get_locale),
) -> Permissions:
    if not perms.allow_aia:
        raise HTTPException(status_code=403, detail=t("auth.aiaForbidden", locale))
    return perms


async def require_workspace_create(
    perms: Permissions = Depends(get_user_permissions),
    locale: str = Depends(get_locale),
) -> Permissions:
    if not perms.allow_workspace_create:
        raise HTTPException(status_code=403, detail=t("auth.workspaceCreateForbidden", locale))
    return perms


def require_tool_access(tool_key: str):
    """Factory for a dependency that checks tool access for a named tool key.

    Usage:
        @router.post("/translate", dependencies=[Depends(require_tool_access("translation"))])
    """
    async def _check(
        perms: Permissions = Depends(get_user_permissions),
        locale: str = Depends(get_locale),
    ) -> Permissions:
        if tool_key not in perms.tools:
            raise HTTPException(status_code=403, detail=t("auth.toolForbidden", locale))
        return perms
    return _check
```

- [ ] **Step 3: Add tests**

```python
# backend/tests/test_permissions.py - APPEND
from src.permissions import resolve_user_permissions


def test_env_admin_overrides_any_role():
    perms = resolve_user_permissions(role="user", custom_role_id=None, is_env_admin=True)
    assert perms.allow_admin_panel is True


def test_unknown_role_falls_back_to_user():
    perms = resolve_user_permissions(role="banana", custom_role_id=None, is_env_admin=False)
    assert perms.allow_admin_panel is False
    assert perms.tools == ()


def test_custom_role_without_id_falls_back_to_user():
    perms = resolve_user_permissions(role="custom", custom_role_id=None, is_env_admin=False)
    assert perms.tools == ()
```

```python
# backend/tests/test_rbac_dependencies.py
"""Integration tests for RBAC FastAPI dependencies."""
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from src.dependencies_rbac import require_admin, require_tool_access, get_user_permissions
from src.permissions import Permissions


@pytest.fixture
def client_with_perms():
    """Build a small app where get_user_permissions is overridden per test."""
    def make(perms: Permissions):
        app = FastAPI()

        @app.get("/admin", dependencies=[Depends(require_admin)])
        def admin_route():
            return {"ok": True}

        @app.get("/translate", dependencies=[Depends(require_tool_access("translation"))])
        def tool_route():
            return {"ok": True}

        async def _override():
            return perms

        app.dependency_overrides[get_user_permissions] = _override
        return TestClient(app)

    return make


def _user_perms():
    from src.permissions import permissions_for_system_role
    return permissions_for_system_role("user")


def _staff_perms():
    from src.permissions import permissions_for_system_role
    return permissions_for_system_role("staff")


def _admin_perms():
    from src.permissions import permissions_for_system_role
    return permissions_for_system_role("admin")


def test_user_blocked_from_admin(client_with_perms):
    r = client_with_perms(_user_perms()).get("/admin")
    assert r.status_code == 403


def test_staff_blocked_from_admin(client_with_perms):
    r = client_with_perms(_staff_perms()).get("/admin")
    assert r.status_code == 403


def test_admin_allowed(client_with_perms):
    r = client_with_perms(_admin_perms()).get("/admin")
    assert r.status_code == 200


def test_user_blocked_from_tool(client_with_perms):
    r = client_with_perms(_user_perms()).get("/translate")
    assert r.status_code == 403


def test_staff_allowed_for_tool(client_with_perms):
    r = client_with_perms(_staff_perms()).get("/translate")
    assert r.status_code == 200
```

- [ ] **Step 4: Add the new i18n keys to `backend/src/i18n.py`**

Open `backend/src/i18n.py` and add to the German + English MESSAGES dicts:

```python
# Add these keys (mirror existing structure):
"auth.aiaForbidden": "Du hast keinen Zugriff auf den AIA-Bereich." (de)
                  / "You do not have access to the AIA area."   (en)
"auth.workspaceCreateForbidden": "Du darfst keine neuen Workspaces erstellen." (de)
                              / "You may not create new workspaces."          (en)
"auth.toolForbidden": "Du darfst dieses Tool nicht nutzen." (de)
                   / "You may not use this tool."          (en)
```

(Insert into the existing `MESSAGES` dict in the same style as `auth.adminRequired`. Exact code edit depends on the file structure — replicate the existing pattern.)

- [ ] **Step 5: Run tests**

Run: `docker compose exec backend pytest backend/tests/test_permissions.py backend/tests/test_rbac_dependencies.py -v`
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add backend/src/dependencies_rbac.py backend/src/permissions.py backend/tests/ backend/src/i18n.py
git commit -m "feat(rbac): permission resolver + FastAPI guard dependencies"
```

---

## Task 5: Wire Session + Auth Status to New Permission Model

**Files:**
- Modify: `backend/src/dependencies.py:32-46`
- Modify: `backend/src/routes/auth.py:18-108`

- [ ] **Step 1: Update `is_admin_user` and `get_admin_user` in dependencies.py**

Replace the existing `is_admin_user` (lines 32-36) and `get_admin_user` (lines 39-46) with:

```python
def is_admin_user(user: dict) -> bool:
    """Return True if the user is admin (env-admin OR has 'admin' role)."""
    settings = get_settings()
    email = (user.get("email") or "").lower()
    if email and settings.admin_email and email == settings.admin_email.lower():
        return True
    return user.get("role") == "admin"


async def get_admin_user(request: Request, locale: str = Depends(get_locale)) -> dict:
    """Like get_current_user, but raises 403 if the user is not an admin.

    Kept for backwards compatibility with existing admin routes; equivalent to
    require_admin from dependencies_rbac.
    """
    user = await get_current_user(request)
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail=t("auth.adminRequired", locale))
    return user
```

- [ ] **Step 2: Update `routes/auth.py` login + status to handle new role values**

In `login` (around line 37-58), replace the `role = ldap_user.get("role", "lecturer")` and the LDAP-derived role flow. We KEEP DB role authoritative; LDAP supplies a default only on first creation:

```python
    # role from LDAP only used if user is brand new; otherwise DB role wins.
    ldap_role_default = ldap_user.get("role", "user")
    if ldap_role_default == "lecturer":
        ldap_role_default = "staff"
    elif ldap_role_default == "student":
        ldap_role_default = "user"
    if ldap_role_default not in ("admin", "staff", "user"):
        ldap_role_default = "user"
```

Then below, where you call `database.create_user(...)` / `database.update_user(...)`, pass `ldap_role_default` only on create. On update, do NOT overwrite the existing DB role. (Adapt the existing call signature accordingly: if `update_user` currently accepts `role`, change the call to omit it or pass a sentinel that means "do not change".)

After fetching `db_user`, fetch the DB-side role so the session uses the authoritative value:

```python
    if db_user is None:
        user_id = database.create_user(ldap_username, display_name, email, active, ldap_role_default)
        effective_role = ldap_role_default
        custom_role_id = None
    else:
        user_id = db_user["id"]
        database.update_user(user_id, display_name, email, active)  # role omitted
        effective_role = db_user.get("role", "user")
        custom_role_id = db_user.get("custom_role_id")
```

Update the session creation and response to include role + custom_role_id:

```python
    token = store.create(data={
        "user_id": user_id,
        "username": ldap_username,
        "display_name": display_name,
        "email": email or "",
        "role": effective_role,
        "custom_role_id": custom_role_id,
    })
    ...
    return {"status": "ok", "username": ldap_username, "display_name": display_name, "role": effective_role}
```

(If `database.update_user` does not currently support omitting the role parameter, add an overload or a new helper `update_user_profile(user_id, display_name, email, active)` that does NOT touch `role`/`custom_role_id`. Use that instead.)

- [ ] **Step 3: Update `auth_status` to include resolved permissions**

Replace `routes/auth.py:auth_status` with:

```python
@router.get("/status")
async def auth_status(request: Request):
    token = request.cookies.get("session")
    if not token:
        return {"authenticated": False}
    store = get_session_store()
    if not store.validate(token):
        return {"authenticated": False}
    data = store.get_data(token) or {}
    settings = get_settings()
    email = (data.get("email") or "").lower()
    is_env_admin = bool(email and settings.admin_email and email == settings.admin_email.lower())

    # Always re-fetch role from DB so revocation is immediate, not next-login.
    user_id = data.get("user_id")
    if user_id:
        db_user = database.get_user_by_id(user_id)
        if db_user:
            data["role"] = db_user.get("role", data.get("role", "user"))
            data["custom_role_id"] = db_user.get("custom_role_id")

    from src.permissions import resolve_user_permissions
    perms = resolve_user_permissions(
        role=data.get("role", "user"),
        custom_role_id=data.get("custom_role_id"),
        is_env_admin=is_env_admin,
    )
    return {
        "authenticated": True,
        "is_admin": perms.allow_admin_panel,
        "role": data.get("role", "user"),
        "custom_role_id": data.get("custom_role_id"),
        "permissions": {
            "allow_admin_panel": perms.allow_admin_panel,
            "allow_aia": perms.allow_aia,
            "allow_workspace_create": perms.allow_workspace_create,
            "tools": list(perms.tools),
        },
        **{k: v for k, v in data.items() if k not in ("role", "custom_role_id")},
    }
```

(If `database.get_user_by_id` does not exist, add it next to `get_user_by_username` in `database.py` with an analogous query.)

- [ ] **Step 4: Manual smoke test**

Run (PowerShell):
```powershell
docker compose restart backend
```

Then in browser, log in as the env-admin and as another user. Hit `/auth/status` (or check Network tab) — verify the response includes `permissions.allow_admin_panel`, `permissions.allow_aia`, `permissions.tools`. For env-admin all true. For a freshly-migrated `staff` user: `allow_admin_panel: false`, `allow_aia: true`, all tools listed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/dependencies.py backend/src/routes/auth.py backend/src/database.py
git commit -m "feat(rbac): wire auth/session to permission resolver, expose perms in /auth/status"
```

---

## Task 6: Apply Permission Guards to Existing Routes

**Files:**
- Modify: All tool route files: `backend/src/routes/translate.py`, `tts.py`, `stt.py`, `image.py`, `summarize.py`, `screencast*.py`, `glossary.py`, `upload.py` (if upload is tool-gated)
- Modify: `backend/src/routes/ai_assistant*.py` files

For each tool route file, add the dependency at router level. Use a separate small step per file to keep diffs reviewable.

- [ ] **Step 1: Gate `translate` route**

In `backend/src/routes/translate.py`, find the `APIRouter(...)` declaration. Change:

```python
router = APIRouter(prefix="/translate", ...)
```

to:

```python
from src.dependencies_rbac import require_tool_access

router = APIRouter(
    prefix="/translate",
    ...,
    dependencies=[Depends(require_tool_access("translation"))],
)
```

(Keep existing `tags`/other kwargs.)

- [ ] **Step 2: Repeat for each tool route**

Apply the same pattern with the matching tool key:
- `tts.py` → `require_tool_access("tts")`
- `stt.py` → `require_tool_access("transcription")`
- `image.py` → `require_tool_access("image")`
- `summarize.py` → `require_tool_access("summary")`
- All `screencast*.py` files → `require_tool_access("screencast")`
- `glossary.py` → `require_tool_access("glossary")`

For `upload.py`: only gate if uploads are tool-context-only. If uploads also serve AIA, leave it open and let the AIA routes do their own gating. **Decision rule:** if the upload route is invoked from a tool page, gate by that tool key; if it's a generic upload helper, gate by `require_aia_access` only when used inside AIA paths.

- [ ] **Step 3: Gate AIA routes**

For each `backend/src/routes/ai_assistant*.py`, add:

```python
from src.dependencies_rbac import require_aia_access, require_workspace_create

router = APIRouter(..., dependencies=[Depends(require_aia_access)])
```

For the *create-workspace* endpoint specifically, add a per-route dependency:

```python
@router.post("/workspaces", dependencies=[Depends(require_workspace_create)])
def create_workspace(...):
    ...
```

(Find the create endpoint by grepping for `POST .* /workspaces` or similar.)

- [ ] **Step 4: Manual smoke test**

Restart backend. As a `user` (the migrated test user that was a student), call `/translate/...` — expect 403. As `staff`, call same — expect 200/normal. As `user`, hit `/ai-assistant/workspaces` — expect 200 (read OK). Try POST to create workspace — expect 403. As `staff` create — expect normal.

- [ ] **Step 5: Commit**

```bash
git add backend/src/routes/
git commit -m "feat(rbac): apply require_tool_access and require_aia_access to all routes"
```

---

## Task 7: Admin API for Custom Roles + User-Role Assignment

**Files:**
- Create: `backend/src/routes/admin/roles.py`
- Modify: `backend/src/routes/admin/users.py`
- Modify: wherever the admin router collects sub-routers (likely `backend/src/app.py` or `backend/src/routes/__init__.py`)
- Test: `backend/tests/test_admin_roles_api.py`

- [ ] **Step 1: Implement admin roles router**

```python
# backend/src/routes/admin/roles.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from src.dependencies_rbac import require_admin
from src.database_roles import (
    list_custom_roles, get_custom_role, create_custom_role,
    update_custom_role, delete_custom_role,
)
from src.tools_registry import ALL_TOOL_KEYS

router = APIRouter(
    prefix="/admin/roles",
    tags=["admin", "roles"],
    dependencies=[Depends(require_admin)],
)


class RolePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    allow_aia: bool = False
    allowed_tools: list[str] = Field(default_factory=list)


def _validate_tools(tool_keys: list[str]) -> list[str]:
    bad = [k for k in tool_keys if k not in ALL_TOOL_KEYS]
    if bad:
        raise HTTPException(status_code=400, detail=f"Unknown tool keys: {bad}")
    # de-dup, preserve order
    seen = set()
    out = []
    for k in tool_keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


@router.get("")
def list_roles():
    return {
        "system_roles": ["admin", "staff", "user"],
        "custom_roles": list_custom_roles(),
        "available_tools": list(ALL_TOOL_KEYS),
    }


@router.post("")
def create_role(payload: RolePayload):
    tools = _validate_tools(payload.allowed_tools)
    new_id = create_custom_role(payload.name.strip(), payload.allow_aia, tools)
    return get_custom_role(new_id)


@router.put("/{role_id}")
def update_role(role_id: int, payload: RolePayload):
    if get_custom_role(role_id) is None:
        raise HTTPException(status_code=404, detail="Role not found")
    tools = _validate_tools(payload.allowed_tools)
    update_custom_role(role_id, payload.name.strip(), payload.allow_aia, tools)
    return get_custom_role(role_id)


@router.delete("/{role_id}")
def delete_role(role_id: int):
    if get_custom_role(role_id) is None:
        raise HTTPException(status_code=404, detail="Role not found")
    delete_custom_role(role_id)
    return {"status": "ok"}
```

- [ ] **Step 2: Add user-role-update endpoint to admin/users.py**

In `backend/src/routes/admin/users.py`, add (after existing endpoints):

```python
from pydantic import BaseModel
from src.database_roles import set_user_role
from src import database
from src.dependencies import get_settings


class UpdateUserRoleBody(BaseModel):
    role: str
    custom_role_id: int | None = None


@router.post("/{user_id}/role")
def update_user_role(user_id: int, body: UpdateUserRoleBody, _admin=Depends(get_admin_user)):
    """Update a user's role.

    Safety rules:
    - Cannot change the env-admin's role (always admin).
    - Cannot demote the LAST admin (env-admin always counts, so this is mostly
      a soft check).
    """
    target = database.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    settings = get_settings()
    email = (target.get("email") or "").lower()
    if settings.admin_email and email == settings.admin_email.lower():
        raise HTTPException(status_code=400, detail="Cannot change role of the env-admin")

    try:
        set_user_role(user_id, body.role, body.custom_role_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok"}
```

- [ ] **Step 3: Register the new admin/roles router**

Locate where admin sub-routers are mounted. In whichever file does `app.include_router(admin_users_router)` (likely `backend/src/app.py`), add the analogous line:

```python
from src.routes.admin import roles as admin_roles
app.include_router(admin_roles.router)
```

- [ ] **Step 4: Add API tests**

```python
# backend/tests/test_admin_roles_api.py
"""End-to-end tests for /admin/roles CRUD.

Uses the existing test app fixture. Skip if the project has no DB-backed
test fixture available — in that case, leave this as manual verification.
"""
# Reduced surface: write only if a usable test app fixture already exists in the project.
# Otherwise leave this file with only this docstring + a single skip marker:
import pytest
pytest.skip("requires DB-backed test app fixture", allow_module_level=True)
```

If the project DOES have a test app + test DB, expand this file with actual create/list/update/delete + 403-as-non-admin tests later.

- [ ] **Step 5: Manual smoke test**

```powershell
# As env-admin (logged in via UI), open browser devtools -> Network and try:
# GET /api/admin/roles    -> { system_roles, custom_roles: [], available_tools: [...] }
# POST /api/admin/roles   body { "name":"Tester","allow_aia":false,"allowed_tools":["screencast","translation"] }
# GET /api/admin/roles    -> includes the new "Tester" role
# DELETE /api/admin/roles/{id}
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/routes/admin/roles.py backend/src/routes/admin/users.py backend/src/app.py backend/tests/test_admin_roles_api.py
git commit -m "feat(rbac): admin API for custom roles + user-role assignment"
```

---

## Task 8: Frontend - AuthStatus Type + Permissions Hook

**Files:**
- Modify: `frontend/src/types/index.ts:1-9`
- Create: `frontend/src/lib/permissions.ts`
- Create: `frontend/src/hooks/usePermissions.ts`

- [ ] **Step 1: Extend AuthStatus type**

Replace `frontend/src/types/index.ts:1-9`:

```typescript
export type SystemRole = "admin" | "staff" | "user" | "custom";

export interface UserPermissions {
  allow_admin_panel: boolean;
  allow_aia: boolean;
  allow_workspace_create: boolean;
  tools: string[]; // tool keys
}

export interface AuthStatus {
  authenticated: boolean;
  user_id?: number;
  username?: string;
  display_name?: string;
  email?: string;
  is_admin?: boolean;
  role?: SystemRole;
  custom_role_id?: number | null;
  permissions?: UserPermissions;
}
```

- [ ] **Step 2: Create permissions.ts helpers**

```typescript
// frontend/src/lib/permissions.ts
import type { UserPermissions } from "@/types";

export const EMPTY_PERMS: UserPermissions = {
  allow_admin_panel: false,
  allow_aia: false,
  allow_workspace_create: false,
  tools: [],
};

export function hasToolAccess(perms: UserPermissions | undefined, toolKey: string): boolean {
  return !!perms?.tools?.includes(toolKey);
}

export function canUseAia(perms: UserPermissions | undefined): boolean {
  return !!perms?.allow_aia;
}

export function canCreateWorkspace(perms: UserPermissions | undefined): boolean {
  return !!perms?.allow_workspace_create;
}

export function isAdmin(perms: UserPermissions | undefined): boolean {
  return !!perms?.allow_admin_panel;
}
```

- [ ] **Step 3: Create usePermissions hook**

```typescript
// frontend/src/hooks/usePermissions.ts
"use client";

import { useEffect, useState } from "react";
import { checkAuthStatus } from "@/lib/auth";
import { EMPTY_PERMS } from "@/lib/permissions";
import type { UserPermissions, SystemRole } from "@/types";

export interface PermissionsState {
  loaded: boolean;
  permissions: UserPermissions;
  role: SystemRole | undefined;
}

export function usePermissions(): PermissionsState {
  const [state, setState] = useState<PermissionsState>({
    loaded: false,
    permissions: EMPTY_PERMS,
    role: undefined,
  });

  useEffect(() => {
    let cancelled = false;
    checkAuthStatus().then((status) => {
      if (cancelled) return;
      setState({
        loaded: true,
        permissions: status.permissions ?? EMPTY_PERMS,
        role: status.role,
      });
    });
    return () => { cancelled = true; };
  }, []);

  return state;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/permissions.ts frontend/src/hooks/usePermissions.ts
git commit -m "feat(rbac): frontend permissions types, helpers, and usePermissions hook"
```

---

## Task 9: Frontend - LockedNotice Component + i18n Keys

**Files:**
- Create: `frontend/src/components/auth/LockedNotice.tsx`
- Modify: `frontend/messages/de.json`
- Modify: `frontend/messages/en.json`

- [ ] **Step 1: Add i18n keys to both message files**

Add to `frontend/messages/de.json` (under appropriate top-level key, e.g. `permissions`):

```json
"permissions": {
  "locked": {
    "aia": "Dieser Bereich ist für deinen Account gesperrt.",
    "tool": "Dieses Tool ist für deinen Account gesperrt.",
    "workspaceCreate": "Du kannst keine neuen Workspaces erstellen — du hast nur Zugriff auf zugewiesene Workspaces."
  }
},
"admin": {
  "roles": {
    "tabLabel": "Rollen",
    "title": "Rollen verwalten",
    "system": "System-Rollen",
    "systemHint": "System-Rollen sind fest definiert und können nicht bearbeitet oder gelöscht werden.",
    "custom": "Eigene Rollen",
    "newRole": "Neue Rolle",
    "name": "Name",
    "allowAia": "AIA-Zugriff",
    "tools": "Globale Tools",
    "save": "Speichern",
    "cancel": "Abbrechen",
    "delete": "Löschen",
    "edit": "Bearbeiten",
    "confirmDelete": "Rolle wirklich löschen? Nutzer mit dieser Rolle werden auf 'user' zurückgesetzt.",
    "userRoleLabel": "Rolle",
    "roleAdmin": "Admin",
    "roleStaff": "Mitarbeiter",
    "roleUser": "Nutzer",
    "roleCustom": "Custom"
  }
}
```

Add the corresponding English versions to `frontend/messages/en.json`:

```json
"permissions": {
  "locked": {
    "aia": "This area is locked for your account.",
    "tool": "This tool is locked for your account.",
    "workspaceCreate": "You cannot create new workspaces — you only have access to assigned workspaces."
  }
},
"admin": {
  "roles": {
    "tabLabel": "Roles",
    "title": "Manage roles",
    "system": "System roles",
    "systemHint": "System roles are fixed and cannot be edited or deleted.",
    "custom": "Custom roles",
    "newRole": "New role",
    "name": "Name",
    "allowAia": "AIA access",
    "tools": "Global tools",
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "edit": "Edit",
    "confirmDelete": "Delete this role? Users with this role will be reset to 'user'.",
    "userRoleLabel": "Role",
    "roleAdmin": "Admin",
    "roleStaff": "Staff",
    "roleUser": "User",
    "roleCustom": "Custom"
  }
}
```

(Merge into existing top-level objects if `permissions`/`admin` already exist.)

- [ ] **Step 2: Implement LockedNotice**

```tsx
// frontend/src/components/auth/LockedNotice.tsx
"use client";

import { Lock } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";

type Variant = "aia" | "tool" | "workspaceCreate";

interface Props {
  variant: Variant;
  className?: string;
}

export default function LockedNotice({ variant, className }: Props) {
  const t = useTranslations("permissions.locked");
  return (
    <div
      role="status"
      className={`flex items-start gap-3 rounded-lg p-4 border ${className ?? ""}`}
      style={{
        background: "var(--surface-dim)",
        borderColor: "var(--border)",
        color: "var(--foreground)",
      }}
    >
      <Lock size={20} weight="bold" style={{ color: "var(--kb)", flexShrink: 0 }} />
      <span className="text-sm leading-relaxed">{t(variant)}</span>
    </div>
  );
}
```

- [ ] **Step 3: Verify i18n consistency**

Run: `cd frontend && npm run check:i18n`
Expected: passes (DE/EN keys aligned).

- [ ] **Step 4: Commit**

```bash
git add frontend/messages/de.json frontend/messages/en.json frontend/src/components/auth/LockedNotice.tsx
git commit -m "feat(rbac): LockedNotice component + permission i18n keys"
```

---

## Task 10: Frontend - Filter Tools Sidebar by Permissions + Update ProtectedRoute

**Files:**
- Modify: `frontend/src/components/layout/ToolsSidebar.tsx:35-77`
- Modify: `frontend/src/components/auth/ProtectedRoute.tsx`

- [ ] **Step 1: Filter ToolsSidebar by permissions**

In `frontend/src/components/layout/ToolsSidebar.tsx`, replace the `useEnabledTools()` block to also intersect with the user's tool permissions. After the existing `const { loaded, isToolEnabled } = useEnabledTools();` line, add:

```typescript
import { usePermissions } from "@/hooks/usePermissions";
// ...
const { loaded: permsLoaded, permissions } = usePermissions();
```

Change the loaded guard:

```typescript
if (!loaded || !permsLoaded || !hydrated) return null;
```

Change the filter:

```typescript
const tools = TOOLS.filter((t) => isToolEnabled(t.key) && permissions.tools.includes(t.key));
```

- [ ] **Step 2: Replace string-role checks in ProtectedRoute**

Rewrite `frontend/src/components/auth/ProtectedRoute.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "@/i18n/navigation";
import { checkAuthStatus } from "@/lib/auth";
import Spinner from "@/components/ui/Spinner";
import { EMPTY_PERMS } from "@/lib/permissions";

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    checkAuthStatus().then((status) => {
      if (!status.authenticated) {
        router.replace("/login");
        setLoading(false);
        return;
      }
      const perms = status.permissions ?? EMPTY_PERMS;
      const isAiaPath = pathname === "/" || pathname?.startsWith("/workspace/");
      const isAdminPath = pathname?.startsWith("/admin");
      const isToolPath = pathname?.startsWith("/tools/");

      // Hard route gates: redirect if the route is structurally not allowed.
      if (isAdminPath && !perms.allow_admin_panel) {
        router.replace("/");
        setLoading(false);
        return;
      }
      if (isToolPath) {
        // tool key is the segment after /tools/, normalised
        const seg = pathname.split("/").filter(Boolean);
        const toolKey = mapPathToToolKey(seg);
        if (toolKey && !perms.tools.includes(toolKey)) {
          router.replace("/");
          setLoading(false);
          return;
        }
      }
      if (isAiaPath && !perms.allow_aia) {
        router.replace("/login");
        setLoading(false);
        return;
      }
      setAuthenticated(true);
      setLoading(false);
    });
  }, [router, pathname]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <Spinner size="lg" />
      </div>
    );
  }
  if (!authenticated) return null;
  return <>{children}</>;
}

function mapPathToToolKey(segs: string[]): string | null {
  // segs example: ["de", "tools", "translate"] - drop locale + "tools"
  const idx = segs.indexOf("tools");
  if (idx === -1) return null;
  const slug = segs[idx + 1];
  if (!slug) return null;
  const map: Record<string, string> = {
    translate: "translation",
    tts: "tts",
    stt: "transcription",
    image: "image",
    summarize: "summary",
    screencast: "screencast",
    "screencast-demo": "screencast",
    glossary: "glossary",
    upload: "", // not a permissioned tool
  };
  return map[slug] ?? null;
}
```

- [ ] **Step 3: Manual smoke test**

Restart frontend (it's running on 3000 already, hot-reload should pick up).

- As `staff`: tools sidebar shows all 7 tools.
- As `user` (former student): sidebar hidden (no tools), `/tools/screencast` redirects to `/`, `/admin` redirects to `/`.
- As `admin`: all visible.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/ToolsSidebar.tsx frontend/src/components/auth/ProtectedRoute.tsx
git commit -m "feat(rbac): filter ToolsSidebar by permissions, replace string-role checks in ProtectedRoute"
```

---

## Task 11: Frontend - Workspace Page Disabled UI for `user` Role

**Files:**
- Modify: `frontend/src/app/[locale]/workspace/_components/LecturerView.tsx`
- (StudentView, if separate, gets the same treatment)

- [ ] **Step 1: Add LockedNotice + disabled "create workspace" affordance**

Open `LecturerView.tsx` (or whichever component renders the home/workspace dashboard for staff/user). At the top:

```typescript
import { usePermissions } from "@/hooks/usePermissions";
import LockedNotice from "@/components/auth/LockedNotice";
```

Inside the component:

```typescript
const { permissions, loaded: permsLoaded } = usePermissions();
const canCreate = permissions.allow_workspace_create;
const aiaAllowed = permissions.allow_aia;
```

If `aiaAllowed` is false (paranoid: ProtectedRoute already redirected), render:

```tsx
if (permsLoaded && !aiaAllowed) {
  return <LockedNotice variant="aia" />;
}
```

For the "Workspace hinzufügen" / create button: wrap or replace with a disabled variant when `!canCreate`:

```tsx
<button
  type="button"
  disabled={!canCreate}
  onClick={canCreate ? handleCreate : undefined}
  title={!canCreate ? t("permissions.locked.workspaceCreate") : undefined}
  className={!canCreate ? "opacity-50 cursor-not-allowed" : ""}
>
  {t("workspace.create")}
</button>
```

(Adapt to the existing button — disable, do not hide. Empty state stays visible.)

If the dashboard renders an inline "create" empty-state CTA, render `<LockedNotice variant="workspaceCreate" />` underneath it.

- [ ] **Step 2: Repeat for StudentView if it exists**

If there's a separate `StudentView.tsx`, the `user` role goes through that view. Make sure it does NOT show "create workspace" affordances; it should ONLY render the list of assigned workspaces. Add `LockedNotice variant="workspaceCreate"` if there's a relevant empty state.

- [ ] **Step 3: Manual smoke test**

- As `staff`: button enabled, can create.
- As `user`: button visible but disabled, tooltip shows the locked message; empty state with `LockedNotice` underneath.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/[locale]/workspace/_components/
git commit -m "feat(rbac): disable workspace creation for 'user' role with lock notice"
```

---

## Task 12: Frontend - Admin Roles Tab + User Role Assignment

**Files:**
- Create: `frontend/src/app/[locale]/admin/_components/RolesTab.tsx`
- Create: `frontend/src/app/[locale]/admin/_components/RoleBuilderDialog.tsx`
- Modify: `frontend/src/app/[locale]/admin/page.tsx`
- Modify: `frontend/src/app/[locale]/admin/_components/UsersTab.tsx`

- [ ] **Step 1: Implement RoleBuilderDialog**

```tsx
// frontend/src/app/[locale]/admin/_components/RoleBuilderDialog.tsx
"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";

interface Role {
  id?: number;
  name: string;
  allow_aia: boolean;
  allowed_tools: string[];
}

interface Props {
  initial: Role | null;          // null = create, otherwise edit
  availableTools: string[];
  onClose: () => void;
  onSaved: () => void;
}

export default function RoleBuilderDialog({ initial, availableTools, onClose, onSaved }: Props) {
  const t = useTranslations("admin.roles");
  const [name, setName] = useState(initial?.name ?? "");
  const [allowAia, setAllowAia] = useState(initial?.allow_aia ?? false);
  const [tools, setTools] = useState<Set<string>>(new Set(initial?.allowed_tools ?? []));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleTool(key: string) {
    const next = new Set(tools);
    if (next.has(key)) next.delete(key); else next.add(key);
    setTools(next);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const payload = { name: name.trim(), allow_aia: allowAia, allowed_tools: Array.from(tools) };
      if (initial?.id) {
        await api.putJson(`/admin/roles/${initial.id}`, payload);
      } else {
        await api.postJson(`/admin/roles`, payload);
      }
      onSaved();
    } catch (e: any) {
      setError(e?.message ?? "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div
        className="w-full max-w-md rounded-lg p-6 space-y-4"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      >
        <h3 className="text-lg font-semibold">{initial?.id ? t("edit") : t("newRole")}</h3>
        <label className="block">
          <span className="text-sm font-medium">{t("name")}</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded border px-2 py-1"
            style={{ borderColor: "var(--border)", background: "var(--background)" }}
          />
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={allowAia} onChange={(e) => setAllowAia(e.target.checked)} />
          <span>{t("allowAia")}</span>
        </label>
        <fieldset>
          <legend className="text-sm font-medium mb-2">{t("tools")}</legend>
          <div className="flex flex-col gap-1">
            {availableTools.map((key) => (
              <label key={key} className="flex items-center gap-2">
                <input type="checkbox" checked={tools.has(key)} onChange={() => toggleTool(key)} />
                <span>{key}</span>
              </label>
            ))}
          </div>
        </fieldset>
        {error && <p className="text-sm" style={{ color: "var(--danger)" }}>{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} disabled={saving}>{t("cancel")}</button>
          <button
            type="button"
            onClick={save}
            disabled={saving || !name.trim()}
            style={{ background: "var(--kb)", color: "white", padding: "0.5rem 1rem", borderRadius: 6 }}
          >
            {t("save")}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Implement RolesTab**

```tsx
// frontend/src/app/[locale]/admin/_components/RolesTab.tsx
"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import RoleBuilderDialog from "./RoleBuilderDialog";

interface CustomRole {
  id: number;
  name: string;
  allow_aia: boolean;
  allowed_tools: string[];
}
interface RolesResponse {
  system_roles: string[];
  custom_roles: CustomRole[];
  available_tools: string[];
}

export default function RolesTab() {
  const t = useTranslations("admin.roles");
  const [data, setData] = useState<RolesResponse | null>(null);
  const [editing, setEditing] = useState<CustomRole | null | undefined>(undefined); // undefined=closed, null=create, value=edit

  async function load() {
    setData(await api.getJson<RolesResponse>("/admin/roles"));
  }

  useEffect(() => { load(); }, []);

  async function remove(role: CustomRole) {
    if (!confirm(t("confirmDelete"))) return;
    await api.delete(`/admin/roles/${role.id}`);
    await load();
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold mb-2">{t("system")}</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>{t("systemHint")}</p>
        <ul className="mt-2 space-y-1">
          {data.system_roles.map((r) => (
            <li key={r} className="text-sm">
              <code>{r}</code>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold">{t("custom")}</h2>
          <button
            type="button"
            onClick={() => setEditing(null)}
            style={{ background: "var(--kb)", color: "white", padding: "0.5rem 1rem", borderRadius: 6 }}
          >
            {t("newRole")}
          </button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr><th className="text-left">{t("name")}</th><th>{t("allowAia")}</th><th>{t("tools")}</th><th></th></tr>
          </thead>
          <tbody>
            {data.custom_roles.map((r) => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td className="text-center">{r.allow_aia ? "✓" : "—"}</td>
                <td>{r.allowed_tools.join(", ") || "—"}</td>
                <td className="text-right">
                  <button onClick={() => setEditing(r)}>{t("edit")}</button>
                  <button onClick={() => remove(r)} className="ml-2">{t("delete")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {editing !== undefined && (
        <RoleBuilderDialog
          initial={editing}
          availableTools={data.available_tools}
          onClose={() => setEditing(undefined)}
          onSaved={() => { setEditing(undefined); load(); }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Register the new tab in admin/page.tsx**

Open `frontend/src/app/[locale]/admin/page.tsx`. Find the tabs array/registry. Add a new entry referencing `RolesTab` with `key: "roles"` and i18n label `admin.roles.tabLabel`. Insert it next to "users".

(The exact code shape depends on how tabs are registered in that file — replicate the pattern of the other tabs.)

- [ ] **Step 4: Add role dropdown in UsersTab**

In `UsersTab.tsx`, for each user row, add a dropdown of available roles. Fetch the roles list once on mount via `GET /admin/roles`. The dropdown shows: `admin`, `staff`, `user`, plus each custom role (`custom:<name>`). On change, POST to `/admin/users/{id}/role` with `{ role: "custom"|"admin"|"staff"|"user", custom_role_id: id|null }`.

Disable the dropdown for the env-admin row (look at the user's email vs the admin email — fetch from `/auth/status` or hardcode-comparable signal). Show a small lock icon next to it with a tooltip explaining why.

- [ ] **Step 5: Manual smoke test**

- As env-admin: open Admin → Rollen tab. Create role "Tester" with `allow_aia=false`, all tool checkboxes ticked. Save. Edit. Delete and recreate.
- Admin → Nutzer tab: change a test-user's role to "Tester". Refresh `/auth/status` for that user (have them re-login or wait for cache TTL). Verify they see all tools but no AIA.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/[locale]/admin/
git commit -m "feat(rbac): admin roles tab and user role dropdown"
```

---

## Task 13: Production Rollout Notes (Manual)

**Files:**
- Create (optional): `private/rbac-rollout.md` — short cheatsheet for the deploy

- [ ] **Step 1: Pre-deploy checklist**

- Backup prod DB.
- Identify the two prod accounts. Note which one is the env-admin (matches `ADMIN_EMAIL`) and which is the second.

- [ ] **Step 2: Deploy**

Push branch, merge, run normal deploy. The schema migration runs automatically on backend boot:
- Migrates `lecturer` → `staff`, `student` → `user`
- Adds `custom_roles` table + `users.custom_role_id`
- Sets default role for new users to `user`

- [ ] **Step 3: Manual role adjustment for the second prod user**

Option A — Admin UI (recommended once UI is deployed):
1. Log in as env-admin
2. Admin Panel → Nutzer tab → find the second user → set role dropdown to `staff` → save

Option B — Direct SQL (if UI is not yet trusted):

```sql
UPDATE users SET role = 'staff', custom_role_id = NULL WHERE email = '<the-other-prod-account@th-luebeck.de>';
```

- [ ] **Step 4: Verify**

- Log in as env-admin: should see admin panel, all tools, AIA.
- Log in as the second user: should see all tools + AIA, NO admin panel.
- (If creating a HiWi-Tester later): create custom role "Tester" with all tools + `allow_aia=false`, assign to the test account, log in and verify locked AIA + tools work.

- [ ] **Step 5: Commit (only if rollout notes file was created)**

```bash
git add private/rbac-rollout.md
git commit -m "docs(rbac): rollout cheatsheet"
```

---

## Self-Review

**Spec coverage:**
- Three system roles, fixed permissions, non-deletable: ✓ (Task 1, 2, 7)
- Single role per user, custom roles as alternative: ✓ (Task 2 schema, Task 7 API)
- Env-admin always admin, never demotable: ✓ (Task 4 resolver, Task 7 user-role API)
- Admin can build custom roles via checkboxes: ✓ (Task 12 UI)
- Backend enforcement on tools + AIA + admin: ✓ (Task 4 deps, Task 6 wiring)
- Frontend disabled UI + lock notice: ✓ (Tasks 9-11)
- Tool registry as single source: ✓ (Task 1 backend, frontend `TOOLS` already canonical)
- Manual prod migration for two accounts: ✓ (Task 13)

**Open follow-ups (not in this plan, intentional):**
- Audit log for role changes
- Custom-role assignment via API to multiple users at once
- Per-tool sub-permissions (deferred per user's "kein granular" decision)
- Auto-provisioning user on first link click for the share flow (the Student-via-Link case may need separate work; this plan only ensures `user` role behaves correctly once the account exists)
