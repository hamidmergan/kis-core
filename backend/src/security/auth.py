from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from src.dependencies import get_settings, get_session_store

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

_OPEN_PATHS = {"/", "/health"}
_OPEN_PREFIXES = ("/auth/",)


async def verify_auth(
    request: Request,
    api_key: str = Security(api_key_header),
):
    """Dual auth: accepts session cookie OR x-api-key header.

    Open paths (landing page, docs, health, auth endpoints) are exempt.
    """
    path = request.url.path
    if path in _OPEN_PATHS or any(path.startswith(p) for p in _OPEN_PREFIXES):
        return

    # 1. Check session cookie
    session_token = request.cookies.get("session")
    if session_token:
        store = get_session_store()
        if store.validate(session_token):
            return

    # 2. Check x-api-key header
    settings = get_settings()
    token = settings.kis_api_token
    if token and api_key == token:
        return

    raise HTTPException(status_code=401, detail="Ungültiger oder fehlender API-Key")
