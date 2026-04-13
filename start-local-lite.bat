@echo off
rem Lokale Entwicklung (lite) — ohne thorsten, ollama, langfuse, adminer, ldapadmin, kokoro (nutzt KISSKI)
rem Nur: redis, postgres, backend, celery-worker, frontend + minio (S3) + ldap (Login)
set PROFILES=--profile minio --profile ldap
set COMPOSE_FILES=-f docker-compose.yml -f docker-compose.override.yml -f docker-compose.gpu.yml

if "%1"=="down" (
    docker compose %COMPOSE_FILES% %PROFILES% down
) else if "%1"=="restart" (
    docker compose %COMPOSE_FILES% %PROFILES% down
    docker compose %COMPOSE_FILES% %PROFILES% up -d --build
    docker image prune -f
    docker volume prune -f
    docker builder prune -f
) else (
    docker compose %COMPOSE_FILES% %PROFILES% up -d --build
    docker image prune -f
    docker volume prune -f
    docker builder prune -f
)
