# Admin: Create LDAP user via UI

**Status:** Design approved (2026-05-08)
**Branch:** `feat/admin-create-ldap-user`
**Scope:** Temporary admin-only feature for local dev + Hetzner. Will be disabled after THL SSO migration.

## Goal

Allow admin to create new LDAP user accounts directly from the admin panel, so test users and Hetzner-prod users can exist without external SSO. Long-term THL users come from SSO and are not managed here.

## Non-goals

- No edit, delete, password-reset, or list-from-LDAP UI (YAGNI; admin already sees synced users in `UsersTab`).
- No bulk import / CSV.
- No email notification with credentials. Admin sees the generated password once and is responsible for handing it over.
- No DB user row created up-front. The user appears in the KIS DB only after first login (existing flow in `routes/auth.py`).

## Decisions (from brainstorming)

| Topic | Decision |
| --- | --- |
| Operations | Create only |
| Access gate | `allow_admin_panel` permission **AND** new env flag `LDAP_USER_CREATION_ENABLED=true` (default false) |
| Password | Backend auto-generates 16-char password (`secrets.token_urlsafe`), hashes to `{SSHA}` for `userPassword`, returns plain password ONCE in response |
| Role | Form has `employeeType` dropdown (`staff` / `student`); existing login flow maps that to KIS role |

## Architecture

```
Admin UI                Backend                       OpenLDAP
--------                -------                       --------
UsersTab "+ Add" -----> POST /api/admin/ldap-users -> add(uid=...,
   button visible       (admin guard +                 cn=..., sn=...,
   only if              feature flag check)            mail=...,
   permissions.                                        employeeType=...,
   allow_ldap_                                         userPassword={SSHA}...)
   user_create
                        generates pw +
                        SSHA hash
                        returns { uid, password } <--- entryAlreadyExists?
                                                       -> 409
   shows pw once
   in success dialog
```

## Components

### Backend

**`backend/src/config.py`** — add setting
```python
ldap_user_creation_enabled: bool = False
```

**`backend/src/ldap_admin.py`** (new file)
- `_make_ssha_hash(password: str) -> str` — stdlib only (`hashlib.sha1` + 4-byte salt + base64), no new dependency. Returns `{SSHA}base64(sha1(pw+salt) + salt)`.
- `_generate_password() -> str` — `secrets.token_urlsafe(12)` (~16 chars).
- `create_ldap_user(uid, given_name, surname, email, employee_type) -> str`:
  1. Validate inputs (regex for uid, email format, employeeType in `{"staff", "student"}`).
  2. Bind as service account using settings.
  3. Build DN: `uid={uid},ou=people,{base_dn}`.
  4. Call `connection.add(dn, ['inetOrgPerson'], attrs)` with `cn = f"{given_name} {surname}"`, `userPassword = {SSHA}...`.
  5. Map `entryAlreadyExists` → raise `LdapUserExists`. Other LDAP errors → `LdapAddError`.
  6. Return generated plain password (never logged).

**`backend/src/routes/admin/ldap_users.py`** (new file, mounted under existing `/api/admin` router)
- `POST /api/admin/ldap-users` — body: `{ uid, given_name, surname, email, employee_type }`.
- Guards: existing admin dep + check `settings.ldap_user_creation_enabled` → `404` if disabled (so feature is invisible).
- On success: `200 { uid, generated_password }`.
- On uid conflict: `409 { detail: t("admin.ldap.userExists") }`.
- On validation error: `400 { detail: ... }`.
- Audit log via `loguru.logger.info("admin {} created LDAP user {}", admin_email, uid)` — no password in log.

**`backend/src/permissions.py`** — extend permission resolver
- Add `allow_ldap_user_create: bool` derived from `allow_admin_panel AND settings.ldap_user_creation_enabled`.
- Surface in `/auth/status` payload `permissions.allow_ldap_user_create`.

**`backend/src/i18n.py`** — new keys (DE + EN)
- `admin.ldap.userExists` — "Benutzer existiert bereits" / "User already exists"
- `admin.ldap.invalidUid` — "Ungültiger Benutzername" / "Invalid username"
- `admin.ldap.addFailed` — "LDAP-Eintrag fehlgeschlagen" / "LDAP add failed"

### Frontend

**`frontend/src/app/[locale]/admin/_components/UsersTab.tsx`**
- Read `permissions.allow_ldap_user_create` from `/auth/status` response.
- In header row, render `+ Benutzer anlegen` button only when flag is true.
- Button opens `CreateLdapUserDialog`.
- After successful create: refresh user list (no-op for DB but keeps pattern), close dialog only after admin closes the password reveal.

**`frontend/src/app/[locale]/admin/_components/CreateLdapUserDialog.tsx`** (new)
- Two-state component: `form` and `success`.
- Form fields: `uid`, `given_name`, `surname`, `email`, `employee_type` (Select staff/student).
- Submit → `POST /api/admin/ldap-users` with `credentials: include`.
- 409 → inline error on `uid` field.
- 200 → switch to `success` state showing:
  - The generated password in a monospace box with a copy button.
  - A prominent warning that it is shown only once.
  - "Schließen" button.

**`frontend/messages/de.json` + `en.json`** — keys under `admin.createLdapUser.*` for title, labels, placeholders, success copy, validation errors.

## Data flow

1. Admin opens UsersTab → `/auth/status` already provides `permissions.allow_ldap_user_create`.
2. Admin clicks button, fills form, submits.
3. Backend validates → binds LDAP service account → `add()` entry with SSHA hash.
4. Returns 200 with `{ uid, generated_password }`.
5. UI shows password once. No DB write yet — first login by the new user triggers the existing `routes/auth.py` flow which creates the DB row using `employeeType` for initial role.

## Error handling

| Failure | Response | UI |
| --- | --- | --- |
| Invalid uid/email | 400 | inline form error |
| uid already exists | 409 | inline error on `uid` field |
| LDAP service bind failed | 500 | toast: "LDAP nicht erreichbar" |
| Other LDAP add error | 500 | toast: generic admin.ldap.addFailed |
| Feature flag off | 404 | (button shouldn't render; defensive) |
| Non-admin | 403 | (existing guard) |

## Testing

- **Manual integration test** against the local `kis-openldap` container: create user, log in as that user via login form, verify DB row created with correct role mapping (`staff` → `staff`, `student` → `user`).
- **Unit test** for `_make_ssha_hash` against a known reference value (verify with python-ldap or ldap3 verify helper).
- **Unit test** for validation: bad uid, bad email, bad employee_type all return 400.
- **No automated test for the LDAP add itself** (bound to live container; covered by manual flow).

## Security

- Generated password: `secrets.token_urlsafe(12)` → ≥16 chars, URL-safe base64 alphabet, ~95 bits of entropy. Sufficient as an initial password handed off in person.
- `userPassword` stored as `{SSHA}` (salted SHA-1) — OpenLDAP standard for `inetOrgPerson` and what existing seeded plain entries are stored as after first authentication.
- Plain password leaves the backend exactly once in the create response. Not logged. Not persisted in KIS DB. Not emailed.
- Endpoint and feature are hidden when env flag is off; enabling requires explicit deploy-time configuration.
- Audit log records who created which uid (no password).

## Migration / rollout

- Default `LDAP_USER_CREATION_ENABLED=false` everywhere.
- Local dev `.env`: set to `true`.
- Hetzner prod `.env`: set to `true` until SSO migration.
- Future THL SSO deploy: leave flag unset → button vanishes; route returns 404. No code change needed to retire.
- No DB migration. No data migration.

## Out of scope (explicit)

- Editing existing LDAP users.
- Deleting LDAP users.
- Password reset for existing LDAP users.
- Listing the LDAP directory in the UI (admin already sees synced users in `UsersTab`).
- Any cross-link between this feature and the SSO migration path.
