#!/bin/sh
# Keeps one SSH tunnel to the nodes of the running HPC jobs and rebuilds it when a job moves to another node.
LOGIN="${HPC_LOGIN:-u26949@glogin-gpu.hpc.gwdg.de}"
# Each entry is local port:job name:port on the node.
MAP="${HPC_TUNNEL_MAP:-18000:kis-llm:28400 18002:kis-stimmen:28402 18003:kis-stimmen:28403 18880:kis-stimmen:28880}"
INTERVAL="${HPC_TUNNEL_INTERVAL:-60}"
OPTS="-i /run/hpc/key -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/state/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=30 -o ServerAliveCountMax=3"

log() { echo "$(date '+%F %T') $*"; }
alive() { [ -n "$pid" ] && [ -r "/proc/$pid/stat" ] && ! grep -q ') Z ' "/proc/$pid/stat"; }

pid=""
current=""
while true; do
  if jobs=$(ssh $OPTS "$LOGIN" "squeue --me -h -t RUNNING -o '%i %j %N'" 2>/tmp/err); then
    forwards=""
    for m in $MAP; do
      port=${m%%:*}; rest=${m#*:}; job=${rest%%:*}; rport=${rest#*:}
      # The newest running job wins, so a successor takes over while its predecessor is still winding down.
      node=$(echo "$jobs" | awk -v j="$job" '$2 == j {print $1, $3}' | sort -n | tail -n 1 | cut -d' ' -f2)
      [ -n "$node" ] && forwards="$forwards -L 0.0.0.0:$port:$node:$rport"
    done
    if [ "$forwards" != "$current" ] || { [ -n "$forwards" ] && ! alive; }; then
      if [ -n "$pid" ]; then kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; pid=""; fi
      current="$forwards"
      if [ -n "$forwards" ]; then
        ssh $OPTS -N -o ExitOnForwardFailure=yes $forwards "$LOGIN" &
        pid=$!
        log "Tunnel:$forwards"
      else
        log "Kein laufender Job"
      fi
    fi
  else
    log "squeue fehlgeschlagen: $(head -c 300 /tmp/err)"
  fi
  sleep "$INTERVAL"
done
