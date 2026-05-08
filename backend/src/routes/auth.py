from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger
from pydantic import BaseModel

from src import database
from src.dependencies import get_settings, get_session_store
from src.i18n import get_locale, t
from src.ldap_auth import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest, response: Response, locale: str = Depends(get_locale)):
    settings = get_settings()

    # Step 1: LDAP authentication
    try:
        ldap_user = authenticate_user(body.username, body.password)
    except RuntimeError as e:
        logger.error("LDAP auth error for user '{}': {}", body.username, e)
        raise HTTPException(status_code=500, detail=str(e))

    if ldap_user is None:
        logger.warning("Failed login attempt for user '{}' (invalid credentials)", body.username)
        raise HTTPException(status_code=401, detail=t("auth.invalidCredentials", locale))

    # Step 2: Determine active status via email whitelist (if enabled)
    ldap_username = ldap_user["username"]  # confirmed by LDAP, not from body
    display_name = ldap_user["fullname"] or ldap_username
    email = ldap_user["email"] or None  # store NULL instead of empty string

    # LDAP-supplied role used only as initial value for brand-new users.
    raw_ldap_role = ldap_user.get("role", "user")
    if raw_ldap_role == "lecturer":
        ldap_role_default = "staff"
    elif raw_ldap_role == "student":
        ldap_role_default = "user"
    elif raw_ldap_role in ("admin", "staff", "user"):
        ldap_role_default = raw_ldap_role
    else:
        ldap_role_default = "user"

    # Maintenance gate: only admin may sign in while maintenance is on.
    maintenance_on = database.get_setting("maintenance_mode", "false").lower() == "true"
    is_admin_email = bool(email and settings.admin_email and email.lower() == settings.admin_email.lower())
    if maintenance_on and not is_admin_email:
        logger.warning("Login blocked for '{}' (maintenance active, non-admin)", ldap_username)
        raise HTTPException(status_code=503, detail=t("maintenance.message", locale))

    whitelist_enabled = database.get_setting("whitelist_enabled", "true").lower() == "true"
    if whitelist_enabled:
        active = 1 if (email and database.is_email_whitelisted(email)) else 0
    else:
        active = 1  # whitelist disabled - all LDAP-authenticated users are allowed

    # Step 3: Sync user with database (create or update)
    db_user = database.get_user_by_username(ldap_username)
    if db_user is None:
        user_id = database.create_user(
            ldap_username, display_name, email, active, ldap_role_default
        )
        effective_role = ldap_role_default
        custom_role_id = None
    else:
        user_id = db_user["id"]
        database.update_user(user_id, display_name, email, active)  # role left intact
        effective_role = db_user.get("role") or "user"
        custom_role_id = db_user.get("custom_role_id")

    # Step 4: Check whitelist
    if not active:
        logger.warning("Login blocked for '{}' (not whitelisted)", ldap_username)
        raise HTTPException(status_code=403, detail="account_not_activated")

    # Step 5: Create session
    store = get_session_store()
    token = store.create(data={
        "user_id": user_id,
        "username": ldap_username,
        "display_name": display_name,
        "email": email or "",
        "role": effective_role,
        "custom_role_id": custom_role_id,
    })
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
        secure=settings.production,
    )
    return {"status": "ok", "username": ldap_username, "display_name": display_name, "role": effective_role}


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session")
    if token:
        store = get_session_store()
        store.destroy(token)
    response.delete_cookie("session")
    return {"status": "ok"}


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

    # Always re-fetch role from DB so role changes apply on next request, not next login.
    user_id = data.get("user_id")
    if user_id:
        db_user = database.get_user_by_id(user_id)
        if db_user:
            data["role"] = db_user.get("role") or data.get("role") or "user"
            data["custom_role_id"] = db_user.get("custom_role_id")

    from src.permissions import resolve_user_permissions
    perms = resolve_user_permissions(
        role=data.get("role", "user"),
        custom_role_id=data.get("custom_role_id"),
        is_env_admin=is_env_admin,
    )
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
    # Preserve other session fields (display_name, username, etc.) without clobbering keys above.
    for k, v in data.items():
        if k not in payload:
            payload[k] = v
    return payload
