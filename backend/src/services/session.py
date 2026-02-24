import hashlib
import hmac
import secrets
import threading
import time


class SessionStore:
    def __init__(self, secret: str, max_age: int = 86400):
        self._secret = secret.encode()
        self._max_age = max_age
        self._sessions: dict[str, float] = {}  # session_id -> expiry timestamp
        self._data: dict[str, dict] = {}        # session_id -> user data
        self._lock = threading.Lock()

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

    def create(self, data: dict | None = None) -> str:
        raw_id = secrets.token_hex(32)
        token = self._sign(raw_id)
        with self._lock:
            self._sessions[raw_id] = time.time() + self._max_age
            if data is not None:
                self._data[raw_id] = data
        return token

    def get_data(self, token: str) -> dict | None:
        raw_id = self._verify(token)
        if raw_id is None:
            return None
        with self._lock:
            return self._data.get(raw_id)

    def validate(self, token: str) -> bool:
        raw_id = self._verify(token)
        if raw_id is None:
            return False
        with self._lock:
            expiry = self._sessions.get(raw_id)
            if expiry is None:
                return False
            if time.time() > expiry:
                del self._sessions[raw_id]
                return False
            return True

    def destroy(self, token: str) -> None:
        raw_id = self._verify(token)
        if raw_id is None:
            return
        with self._lock:
            self._sessions.pop(raw_id, None)
            self._data.pop(raw_id, None)

    def cleanup_expired(self) -> int:
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._sessions.items() if now > v]
            for k in expired:
                del self._sessions[k]
                self._data.pop(k, None)
            return len(expired)
