import sys

from fastapi import Depends, FastAPI
from loguru import logger

from src.dependencies import get_settings
from src.security.auth import verify_auth
from src.routes import auth, health, script, translate, tts


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


def create_app() -> FastAPI:
    _configure_logging()

    settings = get_settings()

    application = FastAPI(
        title="KIS-THL",
        dependencies=[Depends(verify_auth)],
        docs_url="/docs" if not settings.production else None,
        redoc_url="/redoc" if not settings.production else None,
        openapi_url="/openapi.json" if not settings.production else None,
    )

    # Register routers
    application.include_router(auth.router)
    application.include_router(health.router)
    application.include_router(translate.router)
    application.include_router(tts.router)
    application.include_router(script.router)

    logger.info("KIS-THL application started")

    return application


app = create_app()
