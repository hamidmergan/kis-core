#!/usr/bin/env bash
# Baut das Schema EINMAL von null auf und meldet, ob es durchlaeuft.
#
# Warum das nicht der gewoehnliche Start abdeckt: auf einer gewachsenen Datenbank
# sind alle Tabellen laengst da, also faellt es nie auf, wenn eine Anweisung eine
# Tabelle anfasst, die erst weiter unten entsteht. Eine neue Hochschule faengt aber
# mit einer LEEREN Datenbank an, und dort bricht so etwas den ganzen Start ab
# ("relation ... does not exist", Application startup failed).
#
# Gemessen am 2026-08-10 auf dem Server genau so passiert. Deshalb vor jedem
# groesseren Schema-Umbau hier durchlaufen lassen.
#
# Zwei Arten von Fehlern, zwei verschiedene Fixe:
#   * ALTER TABLE ... ADD COLUMN  -> wird auch auf einer frischen Datenbank
#     gebraucht. Die Zieltabelle gehoert VOR die Verwendung gezogen.
#   * UPDATE / DELETE am Altbestand -> auf einer leeren Datenbank gibt es nichts
#     aufzuraeumen. Mit _table_exists() ueberspringen.
#
# Zeigt immer nur den NAECHSTEN Fehler. Nach jedem Fix erneut aufrufen, bis
# "SCHEMA OK" steht.
#
# Aufruf aus dem Projektwurzelverzeichnis:  backend/scripts/check_fresh_schema.sh
set -euo pipefail

DB="${FRESH_SCHEMA_DB:-kis_schematest}"
PW=$(grep -m1 '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)

if [ -z "$PW" ]; then
    echo "POSTGRES_PASSWORD steht nicht in .env" >&2
    exit 1
fi

echo "Lege $DB neu an..."
docker exec kis-postgres psql -U kis -d postgres -q \
    -c "DROP DATABASE IF EXISTS $DB" \
    -c "CREATE DATABASE $DB" >/dev/null

echo "Baue das Schema von null auf..."
docker compose run --rm --no-deps \
    -e DATABASE_URL="postgresql://kis:${PW}@postgres:5432/${DB}" \
    backend python -c "from src.core.db.schema import init_db; init_db(); print('SCHEMA OK auf leerer Datenbank')" \
    2>&1 | grep -vE '^time=|Maschine erkannt|orphan containers'

# Ein Abgleich gegen die gewachsene Datenbank stand hier und ist wieder raus: sie
# traegt tote Spalten aus verworfenen Versuchen, und die tauchten bei jedem Lauf
# als angebliche Luecke auf. Wer das wirklich vergleichen will, macht es von Hand
# und schaut sich jede Zeile an.

echo
echo "Raeume $DB wieder ab."
docker exec kis-postgres psql -U kis -d postgres -q -c "DROP DATABASE IF EXISTS $DB" >/dev/null
