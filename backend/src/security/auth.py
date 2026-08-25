from fastapi import HTTPException, Request
from loguru import logger

from src.dependencies import get_session_store, get_settings
from src.i18n import parse_accept_language, t

_OPEN_PATHS = {"/health", "/health/maintenance", "/health/labels", "/docs", "/redoc", "/openapi.json"}
# Die Einladungsseite gehoert dazu: wer eingeladen wird, hat noch kein Konto und
# kann deshalb keine Sitzung vorzeigen. Der Schluessel im Link ist der Ausweis.
# Die Verwaltung der Einladungen liegt unter /admin/invites und bleibt zu.
_OPEN_PREFIXES = ("/auth/", "/invites/")


async def verify_auth(request: Request):
    """Checks session cookie for authentication.

    In local mode (no LDAP configured): always passes through.
    Open paths (landing page, docs, health, auth endpoints) are exempt.
    """
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
