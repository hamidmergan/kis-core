#!/usr/bin/env bash
# Restore von Postgres + MinIO S3-Bucket aus local-dev/backups/
# Container muessen laufen (start-local.sh).
# ACHTUNG: ueberschreibt existierende Daten.
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

if [ ! -f "$BACKUP_DIR/postgres.dump" ]; then
    echo "local-dev/backups/postgres.dump nicht gefunden." >&2
    exit 1
fi
if [ ! -d "$BACKUP_DIR/minio" ]; then
    echo "local-dev/backups/minio/ nicht gefunden." >&2
    exit 1
fi

echo "ACHTUNG: bestehende Daten in DB $POSTGRES_DB und Bucket $S3_BUCKET werden ueberschrieben."
read -rp "Weiter? (y/N) " CONFIRM
case "$CONFIRM" in
    y|Y) ;;
    *) echo "Abgebrochen."; exit 0 ;;
esac

echo "[1/2] Postgres-Restore aus local-dev/backups/postgres.dump ..."
docker cp "$BACKUP_DIR/postgres.dump" kis-postgres:/tmp/postgres.dump
docker exec kis-postgres sh -c "dropdb -U $POSTGRES_USER --if-exists $POSTGRES_DB && createdb -U $POSTGRES_USER $POSTGRES_DB"
docker exec kis-postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges /tmp/postgres.dump
docker exec kis-postgres rm -f /tmp/postgres.dump

echo "[2/2] MinIO-Bucket $S3_BUCKET aus local-dev/backups/minio/ ..."
docker run --rm --network container:kis-minio \
    -v "$BACKUP_DIR/minio:/data" \
    --entrypoint sh minio/mc \
    -c "mc alias set local http://127.0.0.1:9000 $S3_ACCESS_KEY $S3_SECRET_KEY >/dev/null && mc mb --ignore-existing local/$S3_BUCKET >/dev/null && mc mirror --overwrite --remove --quiet /data local/$S3_BUCKET"

echo
echo "Restore fertig."
