from fastapi import HTTPException, Request
from loguru import logger

from src.dependencies import get_session_store, get_settings
from src.i18n import parse_accept_language, t

_OPEN_PATHS = {"/health", "/health/maintenance", "/health/labels", "/docs", "/redoc", "/openapi.json"}
# The invitation page belongs here, the key in the link is the credential.
_OPEN_PREFIXES = ("/auth/", "/invites/")


async def verify_auth(request: Request):
    """Checks the session cookie, open paths are exempt."""
    settings = get_settings()
    if settings.is_local_mode:
        return

    path = request.url.path
    if path in _OPEN_PATHS or any(path.startswith(p) for p in _OPEN_PREFIXES):
        return

    # Check session cookie
    session_token = request.cookies.get("session")
    if session_token:
        store = get_session_store()
        if store.validate(session_token):
            return
        logger.info("Rejected invalid/expired session on {}", path)
    else:
        logger.debug("Missing session cookie on {}", path)

    locale = parse_accept_language(request.headers.get("accept-language"))
    raise HTTPException(status_code=401, detail=t("auth.notAuthenticated", locale))
