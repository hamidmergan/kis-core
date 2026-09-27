"""Automatic provider retry for the chat stream on a hard upstream error."""

from src.services.openai_compat_llm.base import is_transient_error


def should_failover(e: Exception, *, has_output: bool, is_last_provider: bool) -> bool:
    """Whether a hard chat-provider error should move to the next provider in the chain."""
    return not has_output and not is_last_provider and is_transient_error(e)


def build_client_chain(primary):
    """Only the client itself, its provider door switches to the admin's fallback."""
    return [primary]
