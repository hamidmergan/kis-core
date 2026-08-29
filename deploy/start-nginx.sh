#!/bin/bash
# Hetzner Server — Basis + Production-Nginx
# Aufruf vom Repo-Root: bash deploy/start-nginx.sh [up|down|restart]
cd "$(dirname "$0")/.." || exit 1

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

# Compose startet Dienste mit "profiles" nur, wenn ihr Profil genannt ist.
MODULES_WERT=$(grep -E '^MODULES[[:space:]]*=' .env 2>/dev/null | tail -1 | cut -d= -f2- | cut -d'#' -f1 | tr -d " \"'")
export COMPOSE_PROFILES="${MODULES_WERT:-aia,tools}"
echo "Modul-Profil: $COMPOSE_PROFILES"

CMD=${1:-up}

if [ "$CMD" = "down" ]; then
    docker compose $COMPOSE_FILES down --remove-orphans
elif [ "$CMD" = "restart" ]; then
    docker compose $COMPOSE_FILES down --remove-orphans
    PRODUCTION=true docker compose $COMPOSE_FILES up -d --build
    docker image prune -f
    docker builder prune -af
else
    PRODUCTION=true docker compose $COMPOSE_FILES up -d --build
    docker image prune -f
    docker builder prune -af
fi
