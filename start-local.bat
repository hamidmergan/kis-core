@echo off
rem Lokale Entwicklung — mit NVIDIA GPU
set PROFILES=--profile minio --profile adminer --profile ldap --profile ldapadmin --profile kokoro-gpu --profile ollama --profile langfuse --profile thorsten
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
