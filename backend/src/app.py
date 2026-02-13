from fastapi import Depends, FastAPI

from src.dependencies import get_settings
from src.security.auth import verify_auth
from src.routes import auth, health, script, translate, tts


def create_app() -> FastAPI:
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

    return application


app = create_app()
