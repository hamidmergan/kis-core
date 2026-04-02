#!/bin/bash
# Lokale Entwicklung — alle optionalen Services aktiv
PROFILES="--profile minio --profile adminer --profile ldap --profile ldapadmin --profile kokoro --profile ollama --profile langfuse --profile thorsten"

# Auf macOS: kein NVIDIA, auf Linux/Windows: NVIDIA aktivieren
if [ "$(uname)" = "Darwin" ]; then
    COMPOSE_FILES=""
else
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.override.yml -f docker-compose.gpu.yml"
fi

if [ "$1" = "down" ]; then
    docker compose $COMPOSE_FILES $PROFILES down
elif [ "$1" = "restart" ]; then
    docker compose $COMPOSE_FILES $PROFILES down
    docker compose $COMPOSE_FILES $PROFILES up -d --build
    docker image prune -f
else
    docker compose $COMPOSE_FILES $PROFILES up -d --build
    docker image prune -f
fi
