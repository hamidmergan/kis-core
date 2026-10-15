#!/bin/bash
# isy-kis-thl (THL-Server) — Basis + Frontend, ohne nginx (das macht der THL-nginx)
# Aufruf vom Repo-Root: bash deploy/start-thl.sh [up|down|restart]
cd "$(dirname "$0")/.." || exit 1

# -f explizit, damit ein COMPOSE_FILE aus der .env nichts dazuladen kann.
COMPOSE_FILES="-f docker-compose.yml"

# Compose startet Dienste mit "profiles" nur, wenn ihr Profil genannt ist.
MODULES_WERT=$(grep -E '^MODULES[[:space:]]*=' .env 2>/dev/null | tail -1 | cut -d= -f2- | cut -d'#' -f1 | tr -d " \"'")
export COMPOSE_PROFILES="${MODULES_WERT:-aia,tools},app"
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
