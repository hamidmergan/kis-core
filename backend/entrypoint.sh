#!/bin/sh
# Startet kis-backend. Die Prozesszahl kommt aus den vorhandenen Kernen, damit
# nach einem groesseren Server keine Einstellung von Hand noetig ist.
#
# Steuerung ueber WEB_CONCURRENCY, das ist die uebliche Variable dafuer und wird
# von uvicorn und gunicorn von Haus aus verstanden:
#   nicht gesetzt -> automatisch, Kerne minus eins, hoechstens 8
#   1             -> ein Prozess, wie vor dem Umbau  (NOTAUSSCHALTER)
#   Zahl          -> genau diese Anzahl
# Weil es eine Umgebungsvariable ist, genuegt zum Aendern die .env plus ein
# Neustart des Containers. Kein neues Image bauen.
#
# Mehrere Prozesse sind ueberhaupt erst moeglich, seit alles Geteilte aus dem
# Arbeitsspeicher raus ist:
#   - Anmeldeliste in Redis          (services/session.py)
#   - Upload-Bremse in Redis         (features/ai_assistant/routes/sources/_upload.py)
#   - Schema-Anlegen nur einmal      (app.py, core/db/pool.py run_once_across_processes)
#   - Auftrags-Aufraeumen nur bei leerem Broker (app.py _broker_was_emptied)
#   - Stuendliches Aufraeumen bei celery-beat   (tasks/cleanup_tasks.py)
set -e

KERNE=$(nproc 2>/dev/null || echo 1)

# nproc zaehlt die Kerne des SERVERS, nicht die des Containers. Das stimmt nur,
# solange in der Compose-Datei keine cpu-Grenzen gesetzt sind (heute der Fall).
# Werden spaeter Kerne fest zugeteilt, muss WEB_CONCURRENCY gesetzt werden.
if [ "$KERNE" -gt 2 ]; then
    AUTO=$((KERNE - 1))   # ein Kern bleibt fuer Postgres, Redis und die Worker
else
    AUTO=1
fi
# Nach oben deckeln. Jeder Prozess kostet Arbeitsspeicher, und ab etwa 8 bringt
# mehr kaum noch etwas, weil das Backend ohnehin meist auf fremde Dienste wartet.
[ "$AUTO" -gt 8 ] && AUTO=8

WORKERS="${WEB_CONCURRENCY:-$AUTO}"
# Unsinnige Werte abfangen, damit ein Tippfehler in der .env den Start nicht
# zerlegt (uvicorn wuerde mit --workers 0 oder --workers abc abbrechen).
case "$WORKERS" in
    ''|*[!0-9]*) echo "kis-backend: WEB_CONCURRENCY='$WORKERS' ist keine Zahl, nehme $AUTO"; WORKERS=$AUTO ;;
esac
[ "$WORKERS" -lt 1 ] && WORKERS=1

echo "kis-backend: ${KERNE} Kern(e) erkannt, starte mit ${WORKERS} Prozess(en) (WEB_CONCURRENCY=${WEB_CONCURRENCY:-nicht gesetzt}, Automatik=${AUTO})"

# Bei einem Prozess bewusst OHNE --workers starten. Das ist exakt das bisherige
# Verhalten, ohne zusaetzlichen Aufseher-Prozess davor.
if [ "$WORKERS" -le 1 ]; then
    exec python -m uvicorn src.app:app --host 0.0.0.0 --port 8000
fi

exec python -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --workers "$WORKERS"
