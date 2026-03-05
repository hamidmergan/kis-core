#!/bin/bash
# Lokales Startskript (nicht für Produktion)

EXTRA_PROFILES="--profile minio --profile ldap"

if nvidia-smi &>/dev/null; then
    echo "NVIDIA GPU erkannt -> kokoro-gpu"
    KOKORO_PROFILE="--profile kokoro-gpu"
else
    echo "Kein NVIDIA GPU -> kokoro (CPU)"
    KOKORO_PROFILE="--profile kokoro"
fi

docker compose $EXTRA_PROFILES $KOKORO_PROFILE up -d --build
