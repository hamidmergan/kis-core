#!/bin/bash
# Hetzner Server — Basis + Production-Nginx
# Aufruf vom Repo-Root: bash deploy/start-nginx.sh [up|down|restart]
cd "$(dirname "$0")/.." || exit 1

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
CMD=${1:-up}

if [ "$CMD" = "down" ]; then
    docker compose $COMPOSE_FILES down
elif [ "$CMD" = "restart" ]; then
    docker compose $COMPOSE_FILES down
    PRODUCTION=true docker compose $COMPOSE_FILES up -d --build
    docker image prune -f
    docker builder prune -af
else
    PRODUCTION=true docker compose $COMPOSE_FILES up -d --build
    docker image prune -f
    docker builder prune -af
fi
