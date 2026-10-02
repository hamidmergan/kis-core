from datetime import datetime

from fastapi import HTTPException, Request, Response
from loguru import logger

from src.dependencies import get_session_store, get_settings
from src.i18n import parse_accept_language, t

ACCESS_EXPIRED = "access_expired"

_OPEN_PATHS = {"/health", "/health/maintenance", "/health/labels", "/docs", "/redoc", "/openapi.json"}
# The invitation page and the access code page belong here, both carry their own credential.
# The event pages are open on purpose, their visitors never have an account.
_OPEN_PREFIXES = ("/auth/", "/invites/", "/access-codes/", "/event/")


def access_expired_error() -> HTTPException:
    """403 for a dead test access, taking the useless session cookie with it."""
    # The session itself stays, dropping it would answer its parallel calls with 401.
    blank = Response()
    blank.delete_cookie("session")
    return HTTPException(
        status_code=403,
        detail=ACCESS_EXPIRED,
        headers={"set-cookie": blank.headers["set-cookie"]},
    )


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
        data = store.get_data(session_token)
        if data is not None:
            ablauf = data.get("access_expires_at")
            expired = False
            if ablauf:
                try:
                    expired = datetime.fromisoformat(ablauf) <= datetime.now()
                except (TypeError, ValueError) as e:
                    logger.error("Unparseable access_expires_at '{}' on {}: {}", ablauf, path, e)
            if expired:
                logger.info("Rejected expired test access on {}", path)
                raise access_expired_error()
            return
        logger.info("Rejected invalid/expired session on {}", path)
    else:
        logger.debug("Missing session cookie on {}", path)

    locale = parse_accept_language(request.headers.get("accept-language"))
    raise HTTPException(status_code=401, detail=t("auth.notAuthenticated", locale))
