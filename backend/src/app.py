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
from src.database import init_db, reset_stuck_jobs
from src.core.db.pool import run_once_across_processes
from src.dependencies import get_session_store, get_settings, is_admin_user
from src.security.auth import verify_auth
from src.limits import REQUEST_THREAD_LIMIT
from src.storage import USE_S3, init_storage
from src.routes import admin, auth, glossaries, health, image, invites, jobs, aia, ki_status, me, screencast, screencast_demo, summary, transcription, translate, tts

# Routes that stay reachable during maintenance so the admin can toggle it off
# and users see a clean maintenance page instead of 401/500.
_MAINTENANCE_OPEN_PATHS = {"/health", "/health/maintenance", "/health/labels"}
_MAINTENANCE_OPEN_PREFIXES = ("/admin/", "/auth/")

# Cache maintenance_mode: an uncached get_setting per request serializes the whole
# single-worker app behind a blocking DB round-trip before every dispatch. A few
# seconds of staleness on a maintenance toggle is harmless.
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


# Das stuendliche Aufraeumen lief hier als Endlosschleife (_periodic_cleanup).
# Es liegt jetzt in tasks/cleanup_tasks.py und wird von kis-celery-beat
# angestossen, weil das per Bauart genau einmal laeuft. Mit mehreren
# uvicorn-Prozessen haette hier jeder Prozess seine eigene Schleife gefahren.


# Beliebige feste Zahl, sie muss nur projektweit eindeutig sein.
_LOCK_INIT_DB = 815_001

# Merker in Redis, an dem sich erkennen laesst, ob der Celery-Broker seine
# Warteschlange verloren hat.
_BROKER_MARKER_KEY = "kis:broker:generation"


def _broker_was_emptied() -> bool:
    """True, wenn der Broker leer ist und laufende Auftraege wirklich verwaist sind.

    Warum diese Pruefung ueberhaupt: ``reset_stuck_jobs`` setzt ALLE Auftraege in
    'pending' oder 'running' auf fehlgeschlagen. Das ist richtig, wenn der
    komplette Stapel neu startet, denn dann hat Redis die Warteschlange verloren
    und niemand arbeitet mehr an ihnen.

    Es ist aber falsch in zwei Faellen:
    - Nur kis-backend startet neu. Die Celery-Container laufen weiter und
      arbeiten gerade an genau diesen Auftraegen. Bisher wurden sie trotzdem
      abgebrochen, das war ein Fehler auch schon mit einem Prozess.
    - Mit mehreren uvicorn-Prozessen wuerde JEDER neu gestartete Prozess alle
      laufenden Auftraege der anderen abbrechen.

    Der Merker liegt in Redis, also dort wo auch die Warteschlange liegt. Ist er
    weg, war Redis weg, und dann sind die Auftraege tatsaechlich verwaist.
    ``nx=True`` sorgt dafuer, dass von mehreren gleichzeitig startenden Prozessen
    nur einer True bekommt.

    Bei Redis-Ausfall wird NICHT aufgeraeumt. Lieber bleibt ein Auftrag zu lange
    auf 'running' stehen, als dass gesunde Arbeit abgebrochen wird. Der Waechter
    (watchdog.check, alle 5 Sekunden) faengt wirklich haengende Auftraege
    ohnehin nach JOB_WATCHDOG_MINUTES ueber den Fortschritts-Herzschlag ab.
    """
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
    # Threadpool fuer die `def`-Routen vergroessern. Vorgabe von anyio sind 40,
    # und die gilt fuer ALLE Routen zusammen. Der Wert wird bewusst kleiner
    # gehalten als der DB-Verbindungsvorrat, sonst laeuft der leer und wirft
    # PoolError statt kurz zu warten. Beide Zahlen stehen in limits.py.
    anyio.to_thread.current_default_thread_limiter().total_tokens = REQUEST_THREAD_LIMIT
    logger.info("Request thread pool: {} threads", REQUEST_THREAD_LIMIT)
    # Fail closed: local mode disables ALL authentication (verify_auth passes
    # through, every request becomes admin). That must never happen in prod, so
    # refuse to boot if production is set but no LDAP server is configured
    # (e.g. an env typo or a forgotten LDAP_SERVER var).
    if settings.production and settings.is_local_mode:
        raise RuntimeError(
            "Refusing to start: production=True but LDAP_SERVER is empty. "
            "Local mode would disable authentication entirely."
        )
    # Schema nur von EINEM Prozess anlegen lassen, die anderen warten und
    # ueberspringen, siehe run_once_across_processes().
    with run_once_across_processes(_LOCK_INIT_DB) as am_first:
        if am_first:
            init_db(admin_email=settings.admin_email or None)
            logger.info("Database initialised")
        else:
            logger.info("Database schema already initialised by another process")
    if settings.is_local_mode:
        user_id = db.ensure_local_admin()
        logger.info("Local mode: admin user ensured (id={})", user_id)
    if _broker_was_emptied():
        stuck = reset_stuck_jobs()
        if stuck:
            logger.warning("Startup: {} stuck job(s) reset to failed (broker was empty)", stuck)
    init_storage()
    logger.info("Storage initialised (mode={})", "s3" if USE_S3 else "local")
    if settings.admin_email:
        logger.info("Admin email auto-whitelisted: {}", settings.admin_email)
    yield


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

    def _darf_bei_wartung(data: dict) -> bool:
        """Traegt die Sitzung das Recht auf Zugang waehrend der Wartung?"""
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
        # Admin keeps full access during maintenance so they can keep working.
        # Mirrors is_admin_user(): env-admin OR DB-role 'admin' — otherwise a
        # role='admin' user gets locked out of every non-/admin/ endpoint.
        # Daneben kommt durch, wer das Recht auf Zugang waehrend der Wartung hat.
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
    application.include_router(health.router)
    application.include_router(translate.router)
    application.include_router(image.router)
    application.include_router(tts.router)
    application.include_router(transcription.router)
    application.include_router(screencast.router)
    application.include_router(screencast_demo.router)
    application.include_router(summary.router)
    application.include_router(jobs.router)
    application.include_router(aia.router)
    application.include_router(admin.router)
    application.include_router(ki_status.router)
    application.include_router(me.router)
    application.include_router(glossaries.router)

    return application


app = create_app()
