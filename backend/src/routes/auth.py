from fastapi import APIRouter, HTTPException, Request, Response
from loguru import logger
from pydantic import BaseModel

from src import database
from src.dependencies import get_settings, get_session_store
from src.ldap_auth import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    settings = get_settings()

    # Step 1: LDAP authentication
    try:
        ldap_user = authenticate_user(body.username, body.password)
    except RuntimeError as e:
        logger.error("LDAP auth error for user '{}': {}", body.username, e)
        raise HTTPException(status_code=500, detail=str(e))

    if ldap_user is None:
        logger.warning("Failed login attempt for user '{}' (invalid credentials)", body.username)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Step 2: Determine active status via email whitelist (if enabled)
    ldap_username = ldap_user["username"]  # confirmed by LDAP, not from body
    display_name = ldap_user["fullname"] or ldap_username
    email = ldap_user["email"] or None  # store NULL instead of empty string
    role = ldap_user.get("role", "lecturer")

    whitelist_enabled = database.get_setting("whitelist_enabled", "true").lower() == "true"
    if whitelist_enabled:
        active = 1 if (email and database.is_email_whitelisted(email)) else 0
    else:
        active = 1  # whitelist disabled - all LDAP-authenticated users are allowed

    # Step 3: Sync user with database (create or update)
    db_user = database.get_user_by_username(ldap_username)
    if db_user is None:
        user_id = database.create_user(ldap_username, display_name, email, active, role)
    else:
        user_id = db_user["id"]
        database.update_user(user_id, display_name, email, active, role)

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
        "role": role,
    })
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
        secure=settings.production,
    )
    return {"status": "ok", "username": ldap_username, "display_name": display_name, "role": role}


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
    email = data.get("email", "")
    is_admin = bool(email and email.lower() == settings.admin_email.lower())
    role = data.get("role", "lecturer")
    return {"authenticated": True, "is_admin": is_admin, "role": role, **data}
