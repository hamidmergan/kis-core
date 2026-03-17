#!/bin/bash
# TH Lübeck Server — kein Nginx (eigene Infrastruktur), mit LDAP
PROFILES="-f docker-compose.yml"
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
