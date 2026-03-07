@echo off
docker compose --profile minio --profile adminer --profile ldap --profile kokoro-gpu up -d --build
docker image prune -f
