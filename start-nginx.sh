#!/bin/bash
# Hetzner Server — Nginx + LDAP
PROFILES="-f docker-compose.yml --profile nginx --profile ldap"
CMD=${1:-up}

if [ "$CMD" = "down" ]; then
    docker compose $PROFILES down
elif [ "$CMD" = "restart" ]; then
    docker compose $PROFILES down
    PRODUCTION=true docker compose $PROFILES up -d --build
    docker image prune -f
else
    PRODUCTION=true docker compose $PROFILES up -d --build
    docker image prune -f
fi
