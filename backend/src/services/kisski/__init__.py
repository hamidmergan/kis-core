"""KISSKI LLM Client (OpenAI-kompatibel) — Paket-Aggregation.

Die Client-Klasse wird aus Mixins zusammengesetzt, um die Datei klein zu halten.
Callers importieren weiterhin `from src.services.kisski_client import KisskiClient`
(Wrapper-Modul), oder direkt `from src.services.kisski import KisskiClient`.
"""

from src.services.kisski._scripts import _ScriptsMixin
from src.services.kisski._summary import _SummaryMixin
from src.services.kisski._whisper import _WhisperMixin
from src.services.kisski._whisper_chunked import _WhisperChunkedMixin
from src.services.kisski.base import _KisskiBase


class KisskiClient(
    _WhisperChunkedMixin,
    _WhisperMixin,
    _SummaryMixin,
    _ScriptsMixin,
    _KisskiBase,
):
    """Lightweight wrapper around the KISSKI (GWDG) OpenAI-compatible API."""


__all__ = ["KisskiClient"]
