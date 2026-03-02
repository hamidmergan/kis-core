#!/bin/bash
PRODUCTION=true docker compose up -d --build
docker image prune -f
