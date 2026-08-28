"""Langfuse tracing helper shared by the KI-Assistent routes."""

from langfuse.decorators import langfuse_context


def _trace_llm(llm, name: str) -> None:
    """Update current Langfuse observation with provider metadata."""
    langfuse_context.update_current_observation(
        metadata={"provider": llm._provider, "base_url": llm._base_url, "model": llm._model},
        name=name,
    )
