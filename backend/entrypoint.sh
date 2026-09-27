#!/bin/sh
# Starts kis-backend. The process count comes from the available cores so no
# manual setting is needed after moving to a bigger server.
#
# Controlled by WEB_CONCURRENCY, the usual variable for this, understood by
# uvicorn and gunicorn out of the box:
#   unset  -> automatic, cores minus one, at most 4
#   1      -> one process, as before the rework  (KILL SWITCH)
#   number -> exactly this many
# Because it is an environment variable, changing it needs the .env plus a
# container restart. No new image build.
#
# Several processes are only possible since everything shared left memory:
#   - session list in Redis          (services/session.py)
#   - upload brake in Redis          (features/ai_assistant/routes/sources/_upload.py)
#   - schema creation only once      (app.py, core/db/pool.py run_once_across_processes)
#   - job cleanup only on an empty broker (app.py _broker_was_emptied)
#   - hourly cleanup in celery-beat      (tasks/cleanup_tasks.py)
set -e

KERNE=$(nproc 2>/dev/null || echo 1)

# nproc counts the cores of the SERVER, not of the container. That only holds
# while the compose file sets no cpu limits (the case today). If cores are
# pinned later, WEB_CONCURRENCY has to be set.
if [ "$KERNE" -gt 2 ]; then
    AUTO=$((KERNE - 1))   # ein Kern bleibt fuer Postgres, Redis und die Worker
else
    AUTO=1
fi
# Cap it. Every process costs about 300 MB and the container has 3 GB (mem_limit),
# beyond 4 more barely helps because the backend mostly waits on other services.
[ "$AUTO" -gt 4 ] && AUTO=4

WORKERS="${WEB_CONCURRENCY:-$AUTO}"
# Catch nonsense values so a typo in the .env does not break the start
# (uvicorn would abort on --workers 0 or --workers abc).
case "$WORKERS" in
    ''|*[!0-9]*) echo "kis-backend: WEB_CONCURRENCY='$WORKERS' ist keine Zahl, nehme $AUTO"; WORKERS=$AUTO ;;
esac
[ "$WORKERS" -lt 1 ] && WORKERS=1

echo "kis-backend: ${KERNE} Kern(e) erkannt, starte mit ${WORKERS} Prozess(en) (WEB_CONCURRENCY=${WEB_CONCURRENCY:-nicht gesetzt}, Automatik=${AUTO})"

# With one process start deliberately WITHOUT --workers. That is exactly the
# previous behaviour, without an extra supervisor process in front.
if [ "$WORKERS" -le 1 ]; then
    exec python -m uvicorn src.app:app --host 0.0.0.0 --port 8000
fi

# A process that stalls a few seconds under load (memory pressure, a long request) is not
# killed with every request it is serving: uvicorn's default of 5 seconds did exactly that.
exec python -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --workers "$WORKERS" \
    --timeout-worker-healthcheck 30
