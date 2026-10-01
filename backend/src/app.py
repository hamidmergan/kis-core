import asyncio
import os
import sys
from contextlib import asynccontextmanager

import anyio.to_thread
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src import database as db
from src.database import init_db
from src.core.db.pool import run_once_across_processes
from src.dependencies import get_session_store, get_settings, is_admin_user
from src.modules import MODULE_AIA, MODULE_TOOLS, active_modules
from src.security.auth import verify_auth
from src.limits import REQUEST_THREAD_LIMIT
from src.storage import USE_S3, init_storage
from src.routes import access_codes, admin, auth, evaluation, feedback, glossaries, health, image, interpreter, invites, jobs, aia, ki_status, me, own_interfaces, podcast, praesentation, praesentation_demo, screencast, screencast_demo, summary, summary_demo, transcription, translate, tts

# Routes that stay reachable during maintenance.
_MAINTENANCE_OPEN_PATHS = {"/health", "/health/maintenance", "/health/labels"}
_MAINTENANCE_OPEN_PREFIXES = ("/admin/", "/auth/")

# The value shipped in .env.example, worthless as a real password.
_BEISPIEL_ADMIN_PASSWORT = "adminpw"

# Cache the maintenance flag, otherwise every request waits on a database query.
_MAINTENANCE_TTL_S = 5.0
_maintenance_cache: dict = {"enabled": False, "checked_at": -1e9}


def _configure_logging() -> None:
    """Configure loguru for stdout-only logging (Docker captures stdout)."""
    logger.remove()
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level="INFO",
        colorize=True,
    )


# The hourly cleanup now runs through kis-celery-beat.


# Any fixed number, it only has to be unique project wide.
_LOCK_INIT_DB = 815_001

# Marker in Redis that makes a lost broker recognisable.
_BROKER_MARKER_KEY = "kis:broker:generation"


def _broker_was_emptied() -> bool:
    """True when the broker is empty and running jobs are really orphaned."""
    try:
        import redis as _redis_lib
        r = _redis_lib.from_url(
            os.environ.get("REDIS_URL", "redis://kis-redis:6379/0"),
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        return bool(r.set(_BROKER_MARKER_KEY, "1", nx=True))
    except Exception as e:
        logger.warning("Broker-Merker nicht lesbar, ueberspringe Auftrags-Aufraeumen: {}", e)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Thread pool for def routes, deliberately smaller than the database pool.
    anyio.to_thread.current_default_thread_limiter().total_tokens = REQUEST_THREAD_LIMIT
    logger.info("Request thread pool: {} threads", REQUEST_THREAD_LIMIT)
    # Do not start when production is set but the login is switched off.
    if settings.production and settings.is_local_mode:
        raise RuntimeError(
            "Refusing to start: production=True but AUTH_DISABLED is set. "
            "That would disable authentication entirely."
        )
    # A shipped example password on a real installation is the same as no password.
    if settings.production and settings.admin_password == _BEISPIEL_ADMIN_PASSWORT:
        raise RuntimeError(
            "Refusing to start: production=True but ADMIN_PASSWORD is still the example value."
        )
    # Let only one process create the schema, the others skip it.
    with run_once_across_processes(_LOCK_INIT_DB) as am_first:
        if am_first:
            init_db(admin_email=settings.admin_email or None)
            logger.info("Database initialised")
        else:
            logger.info("Database schema already initialised by another process")
    if settings.is_local_mode:
        user_id = db.ensure_local_admin()
        logger.info("Local mode: admin user ensured (id={})", user_id)
    else:
        from src.features.accounts.env_admin import ensure_env_admin
        ensure_env_admin(settings.admin_email, settings.admin_password, settings.admin_username)
    if _broker_was_emptied():
        from src.services.job_recovery import recover_after_restart
        stuck = recover_after_restart()
        if stuck:
            logger.warning("Startup: {} orphaned job(s) handed to the resume path", stuck)
    init_storage()
    logger.info("Storage initialised (mode={})", "s3" if USE_S3 else "local")
    if settings.admin_email:
        logger.info("Admin email auto-whitelisted: {}", settings.admin_email)
    yield


def create_app(modules=None) -> FastAPI:
    _configure_logging()

    settings = get_settings()
    aktiv = frozenset(modules) if modules is not None else active_modules()

    application = FastAPI(
        title="KIS",
        lifespan=lifespan,
        dependencies=[Depends(verify_auth)],
        docs_url="/docs" if not settings.production else None,
        redoc_url="/redoc" if not settings.production else None,
        openapi_url="/openapi.json" if not settings.production else None,
    )

    @application.middleware("http")
    async def no_cache(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.middleware("http")
    async def local_mode_session(request: Request, call_next) -> Response:
        """Sets a long-lived session cookie in local operation."""
        if not settings.is_local_mode:
            return await call_next(request)

        token = request.cookies.get("session")
        store = get_session_store()
        if token and store.validate(token):
            return await call_next(request)

        local_user = db.get_user_by_username("local")
        if local_user:
            try:
                new_token = store.create(data={
                    "user_id": local_user["id"],
                    "username": "local",
                    "display_name": "Admin",
                    "email": "",
                    "role": "admin",
                    "custom_role_id": None,
                })
            except Exception as e:
                # Best-effort convenience, a hiccup here must not break the request.
                logger.error("Local-mode session creation failed (Redis): {}", e)
                return await call_next(request)
            response = await call_next(request)
            response.set_cookie(
                key="session",
                value=new_token,
                httponly=True,
                samesite="lax",
                max_age=86400 * 365,
            )
            return response

        return await call_next(request)

    def _darf_bei_wartung(data: dict) -> bool:
        """Does the session carry the right to enter during maintenance?"""
        try:
            from src.dependencies_rbac import permissions_of
            from src.permissions_registry import PERM_MAINTENANCE_ACCESS
            return permissions_of(data).has(PERM_MAINTENANCE_ACCESS)
        except Exception:
            return False

    @application.middleware("http")
    async def maintenance_gate(request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if path in _MAINTENANCE_OPEN_PATHS or any(path.startswith(p) for p in _MAINTENANCE_OPEN_PREFIXES):
            return await call_next(request)
        if settings.is_local_mode:
            return await call_next(request)
        loop_now = asyncio.get_running_loop().time()
        if loop_now - _maintenance_cache["checked_at"] >= _MAINTENANCE_TTL_S:
            try:
                _maintenance_cache["enabled"] = (
                    await asyncio.to_thread(db.get_setting, "maintenance_mode", "false")
                ).lower() == "true"
            except Exception:
                _maintenance_cache["enabled"] = False
            _maintenance_cache["checked_at"] = loop_now
        if not _maintenance_cache["enabled"]:
            return await call_next(request)
        # Admins and holders of the maintenance access right still get through.
        token = request.cookies.get("session")
        if token:
            store = get_session_store()
            if store.validate(token):
                data = store.get_data(token) or {}
                if is_admin_user(data) or _darf_bei_wartung(data):
                    return await call_next(request)
        from src.i18n import parse_accept_language, t
        locale = parse_accept_language(request.headers.get("accept-language"))
        return JSONResponse(
            status_code=503,
            content={"maintenance": True, "detail": t("maintenance.message", locale)},
            headers={"Retry-After": "60"},
        )

    # Allow direct browser requests (bypassing Next.js proxy for large uploads)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Subtitles", "X-Audio-Id", "X-Audio-Count"],
    )

    # Register routers
    application.include_router(auth.router)
    application.include_router(invites.router)
    application.include_router(access_codes.router)
    application.include_router(health.router)
    application.include_router(jobs.router)
    application.include_router(admin.router)
    application.include_router(ki_status.router)
    application.include_router(me.router)
    application.include_router(feedback.router)
    application.include_router(evaluation.router)

    if MODULE_TOOLS in aktiv:
        for modul in (translate, interpreter, image, tts, transcription, screencast,
                      screencast_demo, podcast, praesentation, praesentation_demo, summary, summary_demo,
                      glossaries, own_interfaces):
            application.include_router(modul.router)

    if MODULE_AIA in aktiv:
        application.include_router(aia.router)

    return application


app = create_app()
