@echo off
rem Lokale Entwicklung (kia) — nur KIA-relevante Services
rem redis, postgres, backend, celery-worker-kia, minio, ldap (kein frontend, kein celery-screencast/general/beat)
set SERVICES=redis postgres backend celery-worker-kia minio openldap ldap-init
set COMPOSE_FILES=-f docker-compose.yml -f docker-compose.override.yml

if "%1"=="down" (
    docker compose %COMPOSE_FILES% down
) else if "%1"=="restart" (
    docker compose %COMPOSE_FILES% down
    docker compose %COMPOSE_FILES% up -d --build %SERVICES%
    docker image prune -f
    docker volume prune -f
    docker builder prune -f
) else (
    docker compose %COMPOSE_FILES% up -d --build %SERVICES%
    docker image prune -f
    docker volume prune -f
    docker builder prune -f
)
