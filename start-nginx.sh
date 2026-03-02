#!/bin/bash
PRODUCTION=true docker compose --profile nginx --profile ldap up -d --build
docker image prune -f
