#!/bin/bash
# Local development. GPU tweaks are loaded automatically when an NVIDIA driver is
# found, otherwise the stack starts without a GPU.
#
# Modes:
#   ./start-local.sh            fast start (no rebuild)
#   ./start-local.sh build      start with --build (after a Dockerfile/requirements change)
#   ./start-local.sh restart    sledgehammer: down + rebuild + prune
#   ./start-local.sh down       stop the stack + remove orphans

# Only load the GPU compose file when an NVIDIA driver is really there. This used
# to be guessed via uname, which wrongly took every non-macOS for a GPU box.
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.dev.yml"
if command -v nvidia-smi >/dev/null 2>&1; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.gpu.yml"
fi

# Compose startet Dienste mit "profiles" nur, wenn ihr Profil genannt ist.
MODULES_WERT=$(grep -E '^MODULES[[:space:]]*=' .env 2>/dev/null | tail -1 | cut -d= -f2- | cut -d'#' -f1 | tr -d " \"'")
export COMPOSE_PROFILES="${MODULES_WERT:-aia,tools}"
echo "Modul-Profil: $COMPOSE_PROFILES"

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
