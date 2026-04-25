#!/bin/bash
# Lokale Entwicklung — auf macOS ohne GPU, auf Linux/Windows mit NVIDIA GPU
#
# Modi:
#   ./start-local.sh            schneller Start (kein Rebuild)
#   ./start-local.sh build      Start mit --build (nach Dockerfile/requirements-Aenderung)
#   ./start-local.sh restart    Holzhammer: down + Rebuild + Prune
#   ./start-local.sh down       Stack stoppen + Orphans entfernen

if [ "$(uname)" = "Darwin" ]; then
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.override.yml"
else
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.override.yml -f docker-compose.gpu.yml"
fi

frontend_hint() {
    echo
    echo "=== Frontend separat starten: cd frontend && npm run dev ==="
}

if [ "$1" = "down" ]; then
    docker compose $COMPOSE_FILES down --remove-orphans
elif [ "$1" = "build" ]; then
    docker compose $COMPOSE_FILES up -d --build --remove-orphans
    docker image prune -f
    frontend_hint
elif [ "$1" = "restart" ]; then
    docker compose $COMPOSE_FILES down --remove-orphans
    docker compose $COMPOSE_FILES up -d --build
    docker image prune -f
    docker builder prune -f
    frontend_hint
else
    docker compose $COMPOSE_FILES up -d --remove-orphans
    frontend_hint
fi
