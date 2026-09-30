"""What every outside voice client shares: cleaning the text, cutting it and one seat per request."""
from __future__ import annotations

import subprocess

import httpx

from src.i18n import t
from src.services.openai_compat_tts import _split_text
from src.services.tts_number_words import spell_numbers

# Outside services answer within seconds, a minute covers a slow long piece.
REQUEST_TIMEOUT = 90.0
# Checking a key or reading the voices must never hold a page for long.
QUICK_TIMEOUT = 15.0

# Why an outside service refused, the text for each lives under interfaces.error.<code>.
KEY_INVALID = "keyInvalid"
QUOTA = "quota"
# The free use of the service is not open here, it wants a payment account first.
BILLING = "billingRequired"
UNREACHABLE = "unreachable"
REJECTED = "rejected"
# Asking again changes nothing for these two, the person has to act first.
_PERMANENT = frozenset({KEY_INVALID, QUOTA, BILLING})


class OwnInterfaceError(RuntimeError):
    """A refusal of a person's own voice service, readable as it is."""

    def __init__(self, code: str, vendor_label: str, detail: str = "", locale: str = "de"):
        self.code = code
        self.vendor_label = vendor_label
        self.detail = detail
        super().__init__(self.message(locale))

    @property
    def permanent(self) -> bool:
        return self.code in _PERMANENT

    def message(self, locale: str) -> str:
        return t(f"interfaces.error.{self.code}", locale, vendor=self.vendor_label)


def raise_for(response: httpx.Response, vendor_label: str, quota_markers: tuple[str, ...] = ()) -> None:
    """Turns a failed answer into the matching refusal, a success passes."""
    if response.status_code < 400:
        return
    body = response.text[:500]
    lowered = body.lower()
    if quota_markers and any(m in lowered for m in quota_markers):
        raise OwnInterfaceError(QUOTA, vendor_label, body)
    if response.status_code in (401, 403):
        raise OwnInterfaceError(KEY_INVALID, vendor_label, body)
    if response.status_code == 402:
        raise OwnInterfaceError(QUOTA, vendor_label, body)
    if response.status_code == 429 or response.status_code >= 500:
        raise OwnInterfaceError(UNREACHABLE, vendor_label, f"{response.status_code} {body}")
    raise OwnInterfaceError(REJECTED, vendor_label, f"{response.status_code} {body}")


def to_mp3(audio: bytes, sample_rate: int, channels: int = 1, speed: float = 1.0) -> bytes:
    """WAV or raw 16 bit audio as MP3, stretched to the speed when the service knows none of its own."""
    # A WAV names its own format, raw audio needs it spelled out.
    source = [] if audio[:4] == b"RIFF" else ["-f", "s16le", "-ar", str(sample_rate), "-ac", str(channels)]
    tempo = ["-filter:a", f"atempo={min(2.0, max(0.5, speed)):.2f}"] if abs(speed - 1.0) > 0.01 else []
    result = subprocess.run(
        ["ffmpeg", "-v", "error", *source, "-i", "pipe:0", *tempo, "-f", "mp3", "-b:a", "128k", "pipe:1"],
        input=audio, capture_output=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio->MP3 failed: {result.stderr.decode(errors='replace')[-300:]}")
    return result.stdout


class OwnTTSClient:
    """The shape every voice client has in this project, one subclass per outside service."""

    LABEL = ""

    def __init__(self, api_key: str, model: str, binding=None):
        self._api_key = api_key
        self._model = model
        # Without a binding (a key check) the client talks to the service without a seat.
        self._binding = binding

    def _http(self) -> httpx.Client:
        if self._binding is None:
            return httpx.Client(timeout=REQUEST_TIMEOUT)
        from src.services import provider_transport
        return httpx.Client(timeout=REQUEST_TIMEOUT, transport=provider_transport.transport_for(self._binding))

    def _speak(self, client: httpx.Client, text: str, voice_id: str, speed: float) -> bytes:
        """One piece of text as MP3."""
        raise NotImplementedError

    def _one(self, client: httpx.Client, text: str, voice_id: str, speed: float, language: str) -> bytes:
        text = " ".join(line.strip() for line in text.splitlines() if line.strip())
        # Digits would otherwise be read in whatever language the voice guesses.
        text = spell_numbers(text, language)
        if not voice_id or voice_id == "default":
            raise ValueError("voice_id must be set")
        try:
            return self._speak(client, text, voice_id, speed)
        except httpx.TransportError as e:
            raise OwnInterfaceError(UNREACHABLE, self.LABEL, f"{type(e).__name__}: {e}") from e

    def synthesize(self, text: str, language: str = "", *, voice_id: str = "default",
                   speed: float = 1.0, **kwargs) -> bytes:
        with self._http() as client:
            return b"".join(self._one(client, piece, voice_id, speed, language) for piece in _split_text(text))

    def synthesize_chunk(self, text: str, *, voice_id: str = "default", speed: float = 1.0,
                         language: str = "", **kwargs) -> bytes:
        with self._http() as client:
            return self._one(client, text, voice_id, speed, language)

    def synthesize_with_timestamps(self, text: str, language: str = "", *, voice_id: str = "default",
                                   speed: float = 1.0, **kwargs) -> dict:
        return {"audio_bytes": self.synthesize(text, language, voice_id=voice_id, speed=speed),
                "alignment": None}

    def is_available(self) -> bool:
        raise NotImplementedError
