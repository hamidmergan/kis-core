#!/usr/bin/env bash
# Backup von Postgres + MinIO S3-Bucket nach local-dev/backups/
# Container muessen laufen (start-local.sh).
# Nur fuer lokale Entwicklung; wird vor Open-Source-Release entfernt.

set -eu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"
BACKUP_DIR="$SCRIPT_DIR/backups"

if [ ! -f "$ENV_FILE" ]; then
    echo ".env nicht gefunden: $ENV_FILE" >&2
    exit 1
fi

# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a

mkdir -p "$BACKUP_DIR/minio"

echo "[1/2] Postgres-Dump nach local-dev/backups/postgres.dump ..."
docker exec kis-postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/postgres.dump
docker cp kis-postgres:/tmp/postgres.dump "$BACKUP_DIR/postgres.dump"
docker exec kis-postgres rm -f /tmp/postgres.dump

echo "[2/2] MinIO-Bucket $S3_BUCKET nach local-dev/backups/minio/ ..."
docker run --rm --network container:kis-minio \
    -v "$BACKUP_DIR/minio:/data" \
    --entrypoint sh minio/mc \
    -c "mc alias set local http://127.0.0.1:9000 $S3_ACCESS_KEY $S3_SECRET_KEY >/dev/null && mc mirror --overwrite --remove --quiet local/$S3_BUCKET /data"

echo
echo "Backup fertig: $BACKUP_DIR"
