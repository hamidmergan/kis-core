import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.database import init_db
from src.dependencies import get_settings
from src.security.auth import verify_auth
from src.storage import cleanup_expired_files
from src.routes import admin, auth, health, image, jobs, screencast, script, summary, transcription, translate, tts, video_dubbing


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

    # Allow direct browser requests (bypassing Next.js proxy for large uploads)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
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
    application.include_router(script.router)
    application.include_router(transcription.router)
    application.include_router(video_dubbing.router)
    application.include_router(screencast.router)
    application.include_router(summary.router)
    application.include_router(jobs.router)
    application.include_router(admin.router)

    return application


app = create_app()
