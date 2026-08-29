@echo off
rem Lokale Entwicklung mit NVIDIA GPU
rem Frontend laeuft NICHT im Container - in zweitem Terminal: cd frontend && npm run dev
rem
rem Modi:
rem   start-local.bat            schneller Start (kein Rebuild)
rem   start-local.bat build      Start mit --build (nach Dockerfile/requirements-Aenderung)
rem   start-local.bat restart    Holzhammer: down + Rebuild + Prune
rem   start-local.bat down       Stack stoppen + Orphans entfernen

set COMPOSE_FILES=-f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.gpu.yml

rem Compose startet Dienste mit "profiles" nur, wenn ihr Profil genannt ist.
set COMPOSE_PROFILES=aia,tools
for /f "tokens=1,* delims==" %%a in ('findstr /b "MODULES=" .env 2^>nul') do set COMPOSE_PROFILES=%%b
echo Modul-Profil: %COMPOSE_PROFILES%

if "%1"=="down" (
    docker compose %COMPOSE_FILES% down --remove-orphans
) else if "%1"=="build" (
    docker compose %COMPOSE_FILES% up -d --build --remove-orphans
    docker image prune -f
    echo.
    echo === Frontend separat starten: cd frontend ^&^& npm run dev ===
) else if "%1"=="restart" (
    docker compose %COMPOSE_FILES% down --remove-orphans
    docker compose %COMPOSE_FILES% up -d --build
    docker image prune -f
    docker builder prune -f
    echo.
    echo === Frontend separat starten: cd frontend ^&^& npm run dev ===
) else (
    docker compose %COMPOSE_FILES% up -d --remove-orphans
    echo.
    echo === Frontend separat starten: cd frontend ^&^& npm run dev ===
)
