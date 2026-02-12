from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse

from src.dependencies import get_settings
from src.security.auth import verify_auth
from src.routes import auth, health, translate

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="KIS-THL",
        dependencies=[Depends(verify_auth)],
        docs_url="/docs" if not settings.production else None,
        redoc_url="/redoc" if not settings.production else None,
        openapi_url="/openapi.json" if not settings.production else None,
    )

    # Landing page
    @application.get("/", include_in_schema=False)
    async def landing_page():
        return FileResponse(_TEMPLATES_DIR / "index.html", media_type="text/html")

    # Register routers
    application.include_router(auth.router)
    application.include_router(health.router)
    application.include_router(translate.router)

    return application


app = create_app()
