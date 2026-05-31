import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src import database as db
from src.database import init_db, reset_stuck_jobs
from src.dependencies import get_session_store, get_settings, is_admin_user
from src.security.auth import verify_auth
from src.storage import USE_S3, cleanup_expired_files, init_storage
from src.routes import admin, auth, health, image, jobs, aia, ki_status, me, screencast, summary, transcription, translate, tts

# Routes that stay reachable during maintenance so the admin can toggle it off
# and users see a clean maintenance page instead of 401/500.
_MAINTENANCE_OPEN_PATHS = {"/health", "/health/maintenance", "/health/labels"}
_MAINTENANCE_OPEN_PREFIXES = ("/admin/", "/auth/")


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


async def _periodic_cleanup() -> None:
    """Delete expired job files hourly. Prune past schedule entries once per
    day: anything with due_date older than the admin-configured retention is
    removed (checked or not). Setting ``aia_schedule_retention_days`` controls
    the cutoff; -1 (default) disables pruning entirely so entries persist
    forever."""
    DAY_SECS = 24 * 3600
    seconds_since_prune = 0
    while True:
        await asyncio.sleep(3600)
        try:
            deleted = await asyncio.to_thread(cleanup_expired_files)
            if deleted:
                logger.info("Cleanup: {} expired job(s) deleted", deleted)
        except Exception as e:
            logger.warning("Cleanup error: {}", e)
        seconds_since_prune += 3600
        if seconds_since_prune >= DAY_SECS:
            seconds_since_prune = 0
            try:
                raw = db.get_setting("aia_schedule_retention_days", "-1")
                try:
                    retention_days = int(raw)
                except ValueError:
                    retention_days = -1
                if retention_days > 0:
                    pruned = await asyncio.to_thread(db.prune_old_entries, retention_days)
                    if pruned:
                        logger.info(
                            "Schedule cleanup: {} past entries pruned (>{}d)",
                            pruned,
                            retention_days,
                        )
            except Exception as e:
                logger.warning("Schedule cleanup error: {}", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db(admin_email=settings.admin_email or None)
    logger.info("Database initialised")
    if settings.is_local_mode:
        user_id = db.ensure_local_admin()
        logger.info("Local mode: admin user ensured (id={})", user_id)
    stuck = reset_stuck_jobs()
    if stuck:
        logger.warning("Startup: {} stuck job(s) reset to failed (server was restarted)", stuck)
    init_storage()
    logger.info("Storage initialised (mode={})", "s3" if USE_S3 else "local")
    if settings.admin_email:
        logger.info("Admin email auto-whitelisted: {}", settings.admin_email)
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    yield
    cleanup_task.cancel()


def create_app() -> FastAPI:
    _configure_logging()

    settings = get_settings()

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
        """In local mode: inject a long-lived session cookie so Next.js
        layout sees hasSession=true after the first API call."""
        if not settings.is_local_mode:
            return await call_next(request)

        token = request.cookies.get("session")
        store = get_session_store()
        if token and store.validate(token):
            return await call_next(request)

        local_user = db.get_user_by_username("local")
        if local_user:
            new_token = store.create(data={
                "user_id": local_user["id"],
                "username": "local",
                "display_name": "Admin",
                "email": "",
                "role": "admin",
                "custom_role_id": None,
            })
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

    @application.middleware("http")
    async def maintenance_gate(request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if path in _MAINTENANCE_OPEN_PATHS or any(path.startswith(p) for p in _MAINTENANCE_OPEN_PREFIXES):
            return await call_next(request)
        if settings.is_local_mode:
            return await call_next(request)
        try:
            enabled = db.get_setting("maintenance_mode", "false").lower() == "true"
        except Exception:
            enabled = False
        if not enabled:
            return await call_next(request)
        # Admin keeps full access during maintenance so they can keep working.
        # Mirrors is_admin_user(): env-admin OR DB-role 'admin' — otherwise a
        # role='admin' user gets locked out of every non-/admin/ endpoint.
        token = request.cookies.get("session")
        if token:
            store = get_session_store()
            if store.validate(token):
                data = store.get_data(token) or {}
                if is_admin_user(data):
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
    application.include_router(health.router)
    application.include_router(translate.router)
    application.include_router(image.router)
    application.include_router(tts.router)
    application.include_router(transcription.router)
    application.include_router(screencast.router)
    application.include_router(summary.router)
    application.include_router(jobs.router)
    application.include_router(aia.router)
    application.include_router(admin.router)
    application.include_router(ki_status.router)
    application.include_router(me.router)

    return application


app = create_app()
