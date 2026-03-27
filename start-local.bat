@echo off
rem Lokale Entwicklung — alle optionalen Services aktiv
set PROFILES=--profile minio --profile adminer --profile ldap --profile ldapadmin --profile kokoro-gpu --profile ollama --profile langfuse --profile thorsten

if "%1"=="down" (
    docker compose %PROFILES% down
) else if "%1"=="restart" (
    docker compose %PROFILES% down
    docker compose %PROFILES% up -d --build
    docker image prune -f
) else (
    docker compose %PROFILES% up -d --build
    docker image prune -f
)
