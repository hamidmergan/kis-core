#!/bin/sh
# Startet kis-backend. Die Prozesszahl kommt aus den vorhandenen Kernen, damit
# nach einem groesseren Server keine Einstellung von Hand noetig ist.
#
# HIER umstellen, sobald die Anmeldeliste in Redis liegt (services/session.py):
#   MEHRERE_PROZESSE=1
# Vorher NICHT. Heute liegt sie im Arbeitsspeicher EINES Prozesses, Prozess 2
# kennt sie nicht und wuerde Nutzer zufaellig ausloggen.
MEHRERE_PROZESSE=0

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
