"""The OpenAI compatible client, assembled from mixins."""

from src.services.openai_compat_llm._scripts import _ScriptsMixin
from src.services.openai_compat_llm._summary import _SummaryMixin
from src.services.openai_compat_llm._whisper import _WhisperMixin
from src.services.openai_compat_llm._whisper_chunked import _WhisperChunkedMixin
from src.services.openai_compat_llm.base import _OpenAICompatBase


class OpenAICompatLLMClient(
    _WhisperChunkedMixin,
    _WhisperMixin,
    _SummaryMixin,
    _ScriptsMixin,
    _OpenAICompatBase,
):
    """Thin wrapper around an OpenAI compatible endpoint."""


__all__ = ["OpenAICompatLLMClient"]
