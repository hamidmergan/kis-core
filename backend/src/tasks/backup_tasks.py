"""Naechtliche Datenbank-Sicherung in den Objektspeicher.

Warum zusaetzlich zu den Hetzner-Snapshots: ein Snapshot dreht immer den ganzen
Server zurueck. Loescht jemand versehentlich einen Kursraum, waere alles weg was
seit dem Snapshot passiert ist. Aus einem pg_dump kann man dagegen einzelne
Tabellen oder Zeilen zurueckholen und den Rest unberuehrt lassen.

Warum als Celery-Aufgabe und nicht als cron auf dem Server: kis-celery-beat
laeuft per Bauart genau einmal, die Aufgabe steht in git, und der Zugriff auf den
Objektspeicher ist ueber src.storage schon vorhanden. Ein cron-Eintrag auf der
Maschine waere nirgends dokumentiert und beim naechsten Serverwechsel vergessen.

Ablage im gleichen Bucket wie die Nutzdateien, gestaffelt:

    backups/daily/kis-JJJJ-MM-TT.dump     die letzten 7 Naechte
    backups/weekly/kis-JJJJ-Www.dump      die letzten 5 Wochen
    backups/monthly/kis-JJJJ-MM.dump      die letzten 12 Monate

Das ist das verbreitete Grossvater-Vater-Sohn-Schema. Warum drei Stufen und
nicht zwei: ohne die Wochenstufe deckt die Aufbewahrung am 30. eines Monats nur
den 24. bis 30. ab plus den Monatsersten. Ein Fehler vom 10., der am 30.
auffaellt, waere nicht mehr rettbar.

Wochen- und Monatskopie entstehen als serverseitige Kopie im Bucket, die 1,5 GB
gehen also nicht mehrfach ueber die Leitung.

Der Bucket liegt bei Hetzner als eigener Dienst und ueberlebt den Server. Eine
Sicherung auf der Serverplatte waere mit dem Server zusammen verloren. Was der
gemeinsame Bucket NICHT abdeckt: gestohlene Zugangsdaten oeffnen Nutzdateien und
Sicherungen gleichzeitig. Dagegen bleiben die taeglichen Hetzner-Snapshots als
dritte Kopie.

Zurueckspielen, am 2026-07-30 durchgespielt und bestaetigt:

    # Datei aus dem Bucket holen, dann eine einzelne Tabelle in eine
    # Ausweich-Datenbank zurueckholen und von dort die Zeilen kopieren.
    createdb kis_restore_test
    pg_restore -h postgres -U kis -d kis_restore_test -t users --no-owner kis-JJJJ-MM-TT.dump

ERWARTETE MELDUNG dabei, kein Fehler:

    ERROR: unrecognized configuration parameter "transaction_timeout"
    warning: errors ignored on restore: 1

Grund: im Image steckt der Client in Version 17, der Server ist 16. Der Client
schreibt eine Einstellung in die Datei, die der aeltere Server nicht kennt. Sie
wird uebersprungen, die Daten kommen vollstaendig an (geprueft: 8 von 8 Zeilen).
Wichtig nur: NICHT mit ``--exit-on-error`` zurueckspielen, sonst bricht es an
dieser harmlosen Zeile ab.
"""

import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from src.celery_app import celery_app
from src.limits import (
    DB_BACKUP_KEEP_DAYS,
    DB_BACKUP_KEEP_MONTHS,
    DB_BACKUP_KEEP_WEEKS,
    DB_BACKUP_TIME_LIMIT_SECONDS,
)
from src.storage import copy_key, delete_file, list_keys, put_file

_DAILY = "backups/daily/"
_WEEKLY = "backups/weekly/"
_MONTHLY = "backups/monthly/"


def _dump_command_and_env() -> tuple[list[str], dict]:
    """pg_dump-Aufruf aus DATABASE_URL bauen.

    Das Passwort geht ueber die Umgebungsvariable PGPASSWORD, nicht als Argument.
    Argumente sind auf der Maschine fuer jeden per ``ps`` sichtbar, die Umgebung
    eines fremden Prozesses nicht.
    """
    url = urlparse(os.environ["DATABASE_URL"])
    cmd = [
        "pg_dump",
        "-h", url.hostname or "postgres",
        "-p", str(url.port or 5432),
        "-U", url.username or "kis",
        "-d", (url.path or "/kis").lstrip("/"),
        # Eigenformat mit Kompression. Erlaubt spaeter, einzelne Tabellen
        # herauszuholen (pg_restore -t), was das reine SQL-Format nicht kann.
        "-Fc", "-Z6",
    ]
    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = url.password
    return cmd, env


def _prune_old(prefix: str, keep: int) -> int:
    """Sicherungen unter ``prefix`` bis auf die neuesten ``keep`` loeschen.

    Zusaetzlich zur Lebenszyklus-Regel des Buckets, denn die greift nur, wenn der
    Dienstnutzer sie setzen darf (siehe storage.init_lifecycle_policy). Sortiert
    wird nach Namen, nicht nach Datum: der Name beginnt mit dem ISO-Datum und ist
    damit alphabetisch schon chronologisch.
    """
    keys = sorted(k for k in list_keys(prefix) if k.endswith(".dump"))
    if len(keys) <= keep:
        return 0
    veraltet = keys[:-keep]
    for k in veraltet:
        try:
            delete_file(k)
        except Exception as e:
            logger.warning("Alte Sicherung {} nicht loeschbar: {}", k, e)
    return len(veraltet)


def _period_copy_missing(prefix: str, label: str) -> bool:
    """True, wenn fuer diesen Zeitraum noch keine Kopie liegt.

    Bewusst nicht "ist heute Montag" oder "ist heute der Erste": stand der Server
    an dem Tag still, entstuende fuer die Woche oder den Monat sonst nie eine
    Kopie. So holt der naechste Lauf sie nach.
    """
    return not any(k.endswith(f"kis-{label}.dump") for k in list_keys(prefix))


@celery_app.task(
    name="backup.database",
    queue="general",
    time_limit=DB_BACKUP_TIME_LIMIT_SECONDS,
    soft_time_limit=DB_BACKUP_TIME_LIMIT_SECONDS - 60,
)
def run_database_backup() -> dict:
    """Einmal pg_dump, ab in den Bucket, alte Sicherungen aufraeumen."""
    jetzt = datetime.now(timezone.utc)
    tag = jetzt.strftime("%Y-%m-%d")
    # ISO-Woche, damit der Jahreswechsel keine Doppelnamen erzeugt.
    woche = jetzt.strftime("%G-W%V")
    monat = jetzt.strftime("%Y-%m")
    key = f"{_DAILY}kis-{tag}.dump"
    cmd, env = _dump_command_and_env()
    begonnen = time.time()

    with tempfile.TemporaryDirectory(prefix="kis_backup_") as tmp:
        ziel = str(Path(tmp) / "db.dump")
        try:
            subprocess.run(
                cmd + ["-f", ziel],
                env=env,
                check=True,
                capture_output=True,
                timeout=DB_BACKUP_TIME_LIMIT_SECONDS - 120,
            )
        except subprocess.CalledProcessError as e:
            # stderr mitgeben, sonst steht im Logbuch nur "exit 1".
            logger.error("pg_dump fehlgeschlagen: {}", (e.stderr or b"")[:500].decode(errors="replace"))
            raise
        except subprocess.TimeoutExpired:
            logger.error("pg_dump hat die Zeitgrenze ueberschritten")
            raise

        groesse = Path(ziel).stat().st_size
        if groesse == 0:
            # Eine leere Datei hochzuladen waere schlimmer als keine: sie wuerde
            # die Sicherung des Tages ersetzen und wie ein Erfolg aussehen.
            raise RuntimeError("pg_dump lieferte eine leere Datei, Sicherung verworfen")

        put_file(key, ziel)

    dauer = time.time() - begonnen

    # Wochen- und Monatskopie serverseitig im Bucket ziehen, damit die 1,5 GB
    # nicht mehrfach ueber die Leitung gehen.
    kopien = {}
    for stufe, prefix, label in (("weekly", _WEEKLY, woche), ("monthly", _MONTHLY, monat)):
        if not _period_copy_missing(prefix, label):
            kopien[stufe] = None
            continue
        ziel_key = f"{prefix}kis-{label}.dump"
        try:
            copy_key(key, ziel_key)
            kopien[stufe] = ziel_key
        except Exception as e:
            # Die Tagessicherung liegt schon, das ist der wichtigere Teil.
            logger.warning("Kopie {} fehlgeschlagen: {}", ziel_key, e)
            kopien[stufe] = None

    entfernt = {
        "daily": _prune_old(_DAILY, DB_BACKUP_KEEP_DAYS),
        "weekly": _prune_old(_WEEKLY, DB_BACKUP_KEEP_WEEKS),
        "monthly": _prune_old(_MONTHLY, DB_BACKUP_KEEP_MONTHS),
    }
    zusatz = ", ".join(v for v in kopien.values() if v)
    logger.info(
        "Datenbank-Sicherung {} abgelegt ({:.0f} MB in {:.0f}s){}, entfernt: {}",
        key, groesse / 1024 / 1024, dauer,
        f", zusaetzlich {zusatz}" if zusatz else "",
        entfernt,
    )
    return {"key": key, "bytes": groesse, "seconds": round(dauer),
            "copies": kopien, "pruned": entfernt}
