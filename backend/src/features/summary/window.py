"""What window one read call needs and whether the chosen model provably has it."""

from dataclasses import dataclass

from loguru import logger

from src.limits import SUMMARY_WINDOW_PROMPT_TOKENS
from src.services.model_limits import CHARS_PER_TOKEN, ModelProfile


@dataclass(frozen=True)
class WindowVerdict:
    """Whether a file fits in one call, with the numbers a refusal has to name."""

    fits: bool
    measured: bool
    needed_tokens: int
    window_tokens: int


def tokens_needed(chars: int, output_tokens: int) -> int:
    """The file, its answer and the prompt around them, counted in tokens."""
    return int(chars / CHARS_PER_TOKEN) + output_tokens + SUMMARY_WINDOW_PROMPT_TOKENS


def verdict_for(chars: int, output_tokens: int,
                profile: ModelProfile | None) -> WindowVerdict:
    """An unmeasured model is let through, only a measured one can refuse beforehand."""
    gebraucht = tokens_needed(chars, output_tokens)
    if profile is None or not profile.measured:
        return WindowVerdict(True, False, gebraucht, 0)
    return WindowVerdict(profile.window_tokens >= gebraucht, True,
                         gebraucht, profile.window_tokens)


def profile_for_choice(provider_id: int | None) -> ModelProfile | None:
    """The measurement of the model this job runs on, taken now when none is stored."""
    from src.services.model_limits import ensure_profile

    try:
        provider, model = _binding_for(provider_id)
    except Exception as e:  # noqa: BLE001 - an unresolvable choice must not sink the job
        logger.warning("Zusammenfassung: Modell des Auftrags nicht aufloesbar ({})", e)
        return None
    if not provider or not model:
        return None
    try:
        return ensure_profile(provider, model)
    except Exception as e:  # noqa: BLE001 - without a measurement the job simply runs
        logger.warning("Zusammenfassung: Modell nicht vermessbar ({})", e)
        return None


def _binding_for(provider_id: int | None) -> tuple[dict, str]:
    """Provider and model of this job, the same way the caller itself resolves them."""
    if provider_id is not None:
        from src.services.feature_provider_choices import resolve_binding
        binding = resolve_binding("chat", provider_id)
    else:
        from src.services import feature_router
        binding = feature_router.resolve("chat")
    return binding.provider, binding.model or ""
