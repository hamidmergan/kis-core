@echo off
rem Lokale Entwicklung mit NVIDIA GPU
rem Frontend laeuft NICHT im Container - in zweitem Terminal: cd frontend && npm run dev
rem
rem Modi:
rem   start-local.bat            schneller Start (kein Rebuild)
rem   start-local.bat build      Start mit --build (nach Dockerfile/requirements-Aenderung)
rem   start-local.bat restart    Holzhammer: down + Rebuild + Prune
rem   start-local.bat down       Stack stoppen + Orphans entfernen

set COMPOSE_FILES=-f docker-compose.yml -f docker-compose.override.yml -f docker-compose.gpu.yml

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
