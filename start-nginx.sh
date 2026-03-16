#!/bin/bash
PRODUCTION=true docker compose -f docker-compose.yml --profile nginx --profile ldap up -d --build
docker image prune -f
