"""OpenAI-compatible LLM client - package aggregation.

The client class is composed from mixins to keep individual files small.
Callers import via ``from src.services.openai_compat_llm import OpenAICompatLLMClient``.
"""

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
    """Lightweight wrapper around any OpenAI-compatible LLM endpoint.

    The instance is configured with ``base_url``, ``api_key``, ``model`` and
    optional ``provider`` tag. Used today against KISSKI/GWDG, THL myLab and
    Ollama; any other OpenAI-compat backend works just as well.
    """


__all__ = ["OpenAICompatLLMClient"]
