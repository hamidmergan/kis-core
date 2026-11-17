"""The measured context window of the chat model a run writes with."""

from loguru import logger


def measured_window(provider_id: int | None, tool: str) -> int:
    """The window in tokens, 0 when the model was never measured or cannot be reached."""
    from src.services.feature_provider_choices import binding_for
    from src.services.model_limits import ensure_profile

    try:
        binding = binding_for("chat", provider_id)
        profil = ensure_profile(binding.provider, binding.model or "")
        return profil.window_tokens if profil.measured else 0
    except Exception as e:  # noqa: BLE001 - without a measurement the smallest admitted window applies
        logger.warning("{}: Modell nicht vermessbar ({})", tool, e)
        return 0
