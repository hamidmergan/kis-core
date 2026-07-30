#!/bin/sh
# Startet kis-backend. Die Prozesszahl kommt aus den vorhandenen Kernen, damit
# nach einem groesseren Server keine Einstellung von Hand noetig ist.
#
# Mehrere Prozesse sind moeglich, seit alles Geteilte aus dem Arbeitsspeicher
# raus ist:
#   - Anmeldeliste in Redis          (services/session.py)
#   - Upload-Bremse in Redis         (features/ai_assistant/routes/sources/_upload.py)
#   - Schema-Anlegen nur einmal      (app.py, core/db/pool.py run_once_across_processes)
#   - Auftrags-Aufraeumen nur bei leerem Broker (app.py _broker_was_emptied)
#   - Stuendliches Aufraeumen bei celery-beat   (tasks/cleanup_tasks.py)
# Auf 0 stellen, falls doch etwas auffaellt, das ist der Notausschalter.
MEHRERE_PROZESSE=1

set -e

KERNE=$(nproc 2>/dev/null || echo 1)

# nproc zaehlt die Kerne des SERVERS, nicht die des Containers. Das stimmt nur,
# solange in der Compose-Datei keine cpu-Grenzen gesetzt sind (heute der Fall).
if [ "$KERNE" -gt 2 ]; then
    AUTO=$((KERNE - 1))   # ein Kern bleibt fuer Postgres, Redis und die Worker
else
    AUTO=1
fi
# Nach oben deckeln. Jeder Prozess kostet Arbeitsspeicher, und ab etwa 8 bringt
# mehr kaum noch etwas, weil das Backend ohnehin meist auf fremde Dienste wartet.
[ "$AUTO" -gt 8 ] && AUTO=8

[ "$MEHRERE_PROZESSE" = "1" ] && WORKERS=$AUTO || WORKERS=1

echo "kis-backend: ${KERNE} Kern(e) erkannt, starte mit ${WORKERS} Prozess(en)"

# Bei einem Prozess bewusst OHNE --workers starten. Das ist exakt das bisherige
# Verhalten, ohne zusaetzlichen Aufseher-Prozess davor.
if [ "$WORKERS" -le 1 ]; then
    exec python -m uvicorn src.app:app --host 0.0.0.0 --port 8000
fi

exec python -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --workers "$WORKERS"
