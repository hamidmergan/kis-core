import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src import database as db
from src.database import init_db, reset_stuck_jobs
from src.dependencies import get_settings
from src.security.auth import verify_auth
from src.storage import USE_S3, cleanup_expired_files, init_storage
from src.routes import admin, auth, health, image, jobs, ki_tutor, screencast, screencast_demo, summary, transcription, translate, tts

# Routes that stay reachable during maintenance so the admin can toggle it off
# and users see a clean maintenance page instead of 401/500.
_MAINTENANCE_OPEN_PATHS = {"/health", "/health/maintenance"}
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
    """Delete expired job files every hour."""
    while True:
        await asyncio.sleep(3600)
        try:
            deleted = await asyncio.to_thread(cleanup_expired_files)
            if deleted:
                logger.info("Cleanup: {} expired job(s) deleted", deleted)
        except Exception as e:
            logger.warning("Cleanup error: {}", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db(admin_email=settings.admin_email or None)
    logger.info("Database initialised")
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
    async def maintenance_gate(request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if path in _MAINTENANCE_OPEN_PATHS or any(path.startswith(p) for p in _MAINTENANCE_OPEN_PREFIXES):
            return await call_next(request)
        try:
            enabled = db.get_setting("maintenance_mode", "false").lower() == "true"
        except Exception:
            enabled = False
        if enabled:
            return JSONResponse(
                status_code=503,
                content={"maintenance": True, "detail": "Wartungsarbeiten — bitte später erneut versuchen."},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)

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
    application.include_router(screencast_demo.router)
    application.include_router(summary.router)
    application.include_router(jobs.router)
    application.include_router(ki_tutor.router)
    application.include_router(admin.router)

    return application


app = create_app()
