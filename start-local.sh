#!/bin/bash
# Lokale Entwicklung. GPU-Tweaks werden automatisch dazugeladen, wenn ein
# NVIDIA-Treiber gefunden wird, sonst startet der Stack ohne GPU.
#
# Modi:
#   ./start-local.sh            schneller Start (kein Rebuild)
#   ./start-local.sh build      Start mit --build (nach Dockerfile/requirements-Aenderung)
#   ./start-local.sh restart    Holzhammer: down + Rebuild + Prune
#   ./start-local.sh down       Stack stoppen + Orphans entfernen

# GPU-Compose nur laden, wenn wirklich ein NVIDIA-Treiber da ist. Frueher wurde
# per uname geraten, das hielt jedes Nicht-macOS faelschlich fuer eine GPU-Kiste.
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.dev.yml"
if command -v nvidia-smi >/dev/null 2>&1; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.gpu.yml"
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
