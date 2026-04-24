@echo off
rem Lokale Entwicklung mit NVIDIA GPU
rem Frontend laeuft NICHT im Container - in zweitem Terminal: cd frontend && npm run dev
set COMPOSE_FILES=-f docker-compose.yml -f docker-compose.override.yml -f docker-compose.gpu.yml

if "%1"=="down" (
    docker compose %COMPOSE_FILES% down
) else if "%1"=="restart" (
    docker compose %COMPOSE_FILES% down
    docker compose %COMPOSE_FILES% up -d --build
    docker image prune -f
    docker volume prune -f
    docker builder prune -f
    echo.
    echo === Frontend separat starten: cd frontend ^&^& npm run dev ===
) else (
    docker compose %COMPOSE_FILES% up -d --build
    docker image prune -f
    docker volume prune -f
    docker builder prune -f
    echo.
    echo === Frontend separat starten: cd frontend ^&^& npm run dev ===
)
