#!/bin/bash
# Lokale Entwicklung — auf macOS ohne GPU, auf Linux/Windows mit NVIDIA GPU

if [ "$(uname)" = "Darwin" ]; then
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.override.yml"
else
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.override.yml -f docker-compose.gpu.yml"
fi

if [ "$1" = "down" ]; then
    docker compose $COMPOSE_FILES down
elif [ "$1" = "restart" ]; then
    docker compose $COMPOSE_FILES down
    docker compose $COMPOSE_FILES up -d --build
    docker image prune -f
else
    docker compose $COMPOSE_FILES up -d --build
    docker image prune -f
fi
