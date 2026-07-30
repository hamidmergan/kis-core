"""Anmeldesitzungen, gehalten in Redis.

Warum Redis und nicht mehr der Arbeitsspeicher: die Liste lag vorher in zwei
dicts INNERHALB eines Prozesses. Das hatte zwei Folgen. Ein Neustart des
Backends hat jeden Nutzer ausgeloggt, und mehrere uvicorn-Prozesse waren
unmöglich, weil Prozess 2 die Anmeldung von Prozess 1 nicht kannte und Nutzer
zufällig ausgesperrt hätte.

Redis läuft ohnehin im Stapel (Celery-Broker), es kommt also kein Dienst dazu.

Der Token bleibt unverändert aufgebaut: ``<zufalls-id>.<hmac>``. Die Signatur
ist keine Verschlüsselung, sie sortiert nur Müll-Tokens aus, bevor Redis
überhaupt gefragt wird. Die eigentliche Sicherheit steckt in den 32 Zufallsbytes.

Bei Redis-Ausfall wird ZU gemacht, nicht auf. Eine kaputte Sitzungsprüfung darf
niemals versehentlich jeden hereinlassen. Nutzer sehen dann eine Abmeldung,
was ärgerlich aber sicher ist. Anders als die Missbrauchsbremse in
security/rate_limit.py, die bewusst fail-open ist, weil dort die Datenbank die
Wahrheit behält.
"""

import hashlib
import hmac
import json
import os
import secrets

from loguru import logger

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
_KEY_PREFIX = "kis:session:"


class SessionStore:
    def __init__(self, secret: str, max_age: int = 86400):
        self._secret = secret.encode()
        self._max_age = max_age
        self._client = None

    # ─── intern ──────────────────────────────────────────────────────────────

    def _redis(self):
        """Client mit kurzen Zeitgrenzen, gleiches Muster wie rate_limit.py."""
        if self._client is None:
            import redis as _redis_lib
            self._client = _redis_lib.from_url(
                _REDIS_URL, socket_connect_timeout=1, socket_timeout=1
            )
        return self._client

    def _sign(self, data: str) -> str:
        sig = hmac.new(self._secret, data.encode(), hashlib.sha256).hexdigest()
        return f"{data}.{sig}"

    def _verify(self, token: str) -> str | None:
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return None
        data, sig = parts
        expected = hmac.new(self._secret, data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        return data

    # ─── öffentlich ──────────────────────────────────────────────────────────

    def create(self, data: dict | None = None) -> str:
        raw_id = secrets.token_hex(32)
        token = self._sign(raw_id)
        # Die Ablaufzeit macht Redis selbst über die TTL. Absolut ab Erstellung,
        # genau wie vorher, es gibt kein Verlängern bei Aktivität.
        self._redis().set(
            _KEY_PREFIX + raw_id, json.dumps(data or {}), ex=self._max_age
        )
        return token

    def get_data(self, token: str) -> dict | None:
        raw_id = self._verify(token)
        if raw_id is None:
            return None
        try:
            raw = self._redis().get(_KEY_PREFIX + raw_id)
        except Exception as e:
            logger.error("Session read failed (Redis): {}", e)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            logger.error("Session payload is not valid JSON, treating as absent")
            return None

    def validate(self, token: str) -> bool:
        raw_id = self._verify(token)
        if raw_id is None:
            return False
        try:
            return bool(self._redis().exists(_KEY_PREFIX + raw_id))
        except Exception as e:
            # Fail closed, siehe Modulkommentar.
            logger.error("Session check failed (Redis), rejecting: {}", e)
            return False

    def destroy(self, token: str) -> None:
        raw_id = self._verify(token)
        if raw_id is None:
            return
        try:
            self._redis().delete(_KEY_PREFIX + raw_id)
        except Exception as e:
            logger.error("Session delete failed (Redis): {}", e)
