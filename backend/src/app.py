from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse

from src.dependencies import get_settings
from src.security.auth import verify_auth
from src.routes import auth, health, translate

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="kis-thl - Dokumentübersetzung",
        dependencies=[Depends(verify_auth)],
        docs_url=None,
        redoc_url=None if not settings.enable_docs else "/redoc",
        openapi_url=None if not settings.enable_docs else "/openapi.json",
    )


    # Custom Swagger UI with password field (only in development)
    if settings.enable_docs:
        @application.get("/docs", include_in_schema=False)
        async def custom_swagger_docs():
            response = get_swagger_ui_html(
                openapi_url=application.openapi_url,
                title=f"{application.title} - Docs",
            )
            patch_script = """
<script>
(function () {
  const obs = new MutationObserver(() => {
    document.querySelectorAll('.auth-container input[type="text"]').forEach(el => {
      el.setAttribute('type', 'password');
      el.setAttribute('autocomplete', 'off');
    });
  });
  obs.observe(document.body, { childList: true, subtree: true });
})();
</script>"""
            html = response.body.decode()
            html = html.replace("</body>", patch_script + "\n</body>")
            return HTMLResponse(html)

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
