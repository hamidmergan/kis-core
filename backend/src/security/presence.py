"""Wer gerade da ist, und an welchen Tagen jemand da war.

Angemeldet ist nicht online: der Sitzungsschluessel laeuft 24 Stunden ab der
Anmeldung, nicht ab der letzten Handlung (siehe services/session.py). Wer sich
morgens anmeldet und den Laptop zuklappt, gaelte damit bis zum naechsten Morgen
als anwesend.

Der Herzschlag kommt deshalb von der Leitung, die der Auftrags-Stream ohnehin
fuer jeden offenen Tab offen haelt: sie schickt alle paar Sekunden ein Ping,
damit Proxys sie nicht kappen. Dort steht die Nutzer-Nummer, sie wurde nur nie
festgehalten. Genau da setzt dieses Modul an, ohne eine einzige neue Abfrage.

Zwei Ablagen mit zwei Zwecken:

- Redis mit kurzer Frist beantwortet "wer ist jetzt online". Faellt Redis aus,
  ist die Antwort leer statt falsch, und niemand merkt es an anderer Stelle.
- Eine Zeile je Nutzer und Stunde in der Datenbank beantwortet "wie viele waren
  gestern da". Die bleibt, auch wenn Redis neu startet.

Fire-and-forget: ein Fehler beim Mitschreiben darf nie den Stream reissen, an
dem ein Nutzer gerade haengt.
"""
import os
import time
from datetime import datetime, timezone

from loguru import logger

from src.core.db.pool import get_connection

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
_PREFIX = "kis:seen:"

# Ein Wert unter dieser Marke kann kein Zeitpunkt sein. Fruehere Fassungen
# schrieben eine schlichte "1" in den Schluessel, und daraus wuerden Millionen
# Minuten. Solche Schluessel gelten als eben erst gesetzt.
_FRUEHESTENS = 1_600_000_000  # September 2020

# Wie lange ein Lebenszeichen zaehlt. Fuenf Minuten, weil der Stream alle zwanzig
# Sekunden pingt: eine kurze Stoerung der Leitung soll niemanden sofort als weg
# zaehlen, eine geschlossene Seite aber schon.
TTL_SECONDS = 300

_client = None


def _redis():
    global _client
    if _client is None:
        import redis as _redis_lib
        _client = _redis_lib.from_url(
            _REDIS_URL, socket_connect_timeout=1, socket_timeout=1
        )
    return _client


def touch(user_id: int) -> None:
    """Ein Lebenszeichen. Wird aus der Ping-Schleife des Streams gerufen.

    Im Schluessel steht der Zeitpunkt des ERSTEN Lebenszeichens, nicht des
    letzten: daraus wird "seit wann online". Deshalb zwei Schritte, ``nx``
    schreibt nur beim ersten Mal, ``expire`` schiebt die Frist bei jedem Ping.
    """
    if user_id <= 0:
        return
    try:
        r = _redis()
        schluessel = f"{_PREFIX}{user_id}"
        r.set(schluessel, str(int(time.time())), nx=True, ex=TTL_SECONDS)
        r.expire(schluessel, TTL_SECONDS)
    except Exception as e:
        logger.warning("Anwesenheit nicht gemerkt (user={}): {}", user_id, e)


def online_user_ids() -> list[int]:
    """Wer in den letzten fuenf Minuten ein Lebenszeichen gegeben hat."""
    return sorted(online_since().keys())


def online_since() -> dict[int, int]:
    """Nutzernummer auf den Zeitpunkt des ersten Lebenszeichens, in Sekunden.

    Bei Redis-Ausfall leer. Eine Statistik, die kurz nichts anzeigt, ist besser
    als eine, die raet.
    """
    try:
        r = _redis()
        keys = r.keys(f"{_PREFIX}*")
        if not keys:
            return {}
        werte = r.mget(keys)
        ergebnis: dict[int, int] = {}
        for k, v in zip(keys, werte):
            if v is None:
                continue
            try:
                nummer = int(k.decode().rsplit(":", 1)[1])
                zeitpunkt = int(v)
            except (ValueError, AttributeError):
                continue
            ergebnis[nummer] = zeitpunkt if zeitpunkt >= _FRUEHESTENS else int(time.time())
        return ergebnis
    except Exception as e:
        logger.warning("Anwesenheit nicht lesbar: {}", e)
        return {}


def mark_hour(user_id: int) -> None:
    """Diese Stunde fuer diesen Nutzer festhalten. Hoechstens eine Zeile je Stunde.

    Aus diesen Zeilen faellt spaeter beides heraus: wie viele an einem Tag da
    waren, und wie sich ein Tag ueber die Stunden verteilt.
    """
    if user_id <= 0:
        return
    jetzt = datetime.now(timezone.utc)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO user_presence (user_id, day, hour)
                       VALUES (
                           %s,
                           (%s AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date,
                           EXTRACT(HOUR FROM (%s AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin'))
                       )
                       ON CONFLICT (user_id, day, hour) DO NOTHING""",
                    (user_id, jetzt, jetzt),
                )
            conn.commit()
    except Exception as e:
        logger.warning("Anwesenheitsstunde nicht gemerkt (user={}): {}", user_id, e)
