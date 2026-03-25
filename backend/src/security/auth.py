from fastapi import HTTPException, Request

from src.dependencies import get_session_store

_OPEN_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}
_OPEN_PREFIXES = ("/auth/",)


async def verify_auth(request: Request):
    """Checks session cookie for authentication.

    Open paths (landing page, docs, health, auth endpoints) are exempt.
    """
    path = request.url.path
    if path in _OPEN_PATHS or any(path.startswith(p) for p in _OPEN_PREFIXES):
        return

    # Check session cookie
    session_token = request.cookies.get("session")
    if session_token:
        store = get_session_store()
        if store.validate(session_token):
            return

    raise HTTPException(status_code=401, detail="Nicht authentifiziert")
