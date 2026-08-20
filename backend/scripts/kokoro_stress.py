#!/usr/bin/env python3
"""Kokoro TTS concurrency stress test — no external deps (urllib + threads).

Run ON the box that can reach the endpoint (e.g. the prod host where the autossh
tunnel kokoro-tunnel.service exposes the GPU Kokoro). Fires bursts at
rising concurrency and reports per-request latency, throughput and errors — so you
can see whether the GPU server PARALLELISES concurrent requests or serialises them
(the local CPU container serialises: C=8 took 8x as long).

Usage:
    python3 kokoro_stress.py                       # uses $KOKORO_BASE_URL
    python3 kokoro_stress.py http://172.18.0.1:8880
    KOKORO_BASE_URL=http://127.0.0.1:8880 python3 kokoro_stress.py

Env: KOKORO_BASE_URL, KOKORO_VOICE (default af_sky), KOKORO_MODEL (default kokoro),
     KOKORO_LEVELS (default "1,2,4,8,16").
"""
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("KOKORO_BASE_URL", "http://127.0.0.1:8880")).rstrip("/")
VOICE = os.environ.get("KOKORO_VOICE", "af_sky")
MODEL = os.environ.get("KOKORO_MODEL", "kokoro")
LEVELS = [int(x) for x in os.environ.get("KOKORO_LEVELS", "1,2,4,8,16").split(",")]
TEXT = ("Die automatische Sprachsynthese wandelt geschriebenen Text in gesprochene Sprache um. "
        "Dieser Absatz dient als realistische Testlast fuer den Kokoro-Dienst unter gleichzeitiger Nutzung. "
        "Wir messen Latenz, Durchsatz und Fehler bei steigender Parallelitaet.")


def one(_i):
    body = json.dumps({"model": MODEL, "input": TEXT, "voice": VOICE, "response_format": "mp3"}).encode()
    req = urllib.request.Request(f"{BASE}/v1/audio/speech", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return (r.status, time.time() - t0, len(r.read()))
    except Exception as e:  # noqa: BLE001
        return ("ERR", time.time() - t0, str(e)[:80])


def main():
    print(f"endpoint={BASE} voice={VOICE} model={MODEL} input_chars={len(TEXT)}")
    try:
        one(0)  # warmup
    except Exception as e:  # noqa: BLE001
        print("warmup failed:", e); return
    print(f"{'C':>3} {'wall':>7} {'ok':>6} {'lat_avg':>8} {'lat_min':>8} {'lat_max':>8} {'req/s':>7}  errs")
    for c in LEVELS:
        t0 = time.time()
        res = []
        with ThreadPoolExecutor(max_workers=c) as ex:
            for f in as_completed([ex.submit(one, i) for i in range(c)]):
                res.append(f.result())
        wall = time.time() - t0
        ok = [r for r in res if r[0] == 200]
        lat = [r[1] for r in ok] or [0]
        errs = [r for r in res if r[0] != 200]
        print(f"{c:>3} {wall:>6.1f}s {len(ok):>4}/{c:<1} {sum(lat)/len(lat):>7.1f}s "
              f"{min(lat):>7.1f}s {max(lat):>7.1f}s {len(ok)/wall if wall else 0:>6.2f}  {len(errs)}")
        if errs:
            print("    ERR sample:", errs[0])


if __name__ == "__main__":
    main()
