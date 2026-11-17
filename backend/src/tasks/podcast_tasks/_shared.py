"""What both podcast tasks need."""

from src.tasks._cancel import clear_cancel, is_cancelled  # noqa: F401 - clear_cancel is imported from here


class JobCancelled(Exception):
    """The person pressed cancel, this is not a fault."""


def assert_not_cancelled(job_uuid: str) -> None:
    if is_cancelled(job_uuid):
        raise JobCancelled()


def tts_client(provider_id: int, user_id: int | None = None):
    """The voice provider of this run, the same resolver the screencast uses."""
    from src.dependencies import get_tts_client_for_provider

    client = get_tts_client_for_provider(provider_id, user_id)
    if client is None:
        raise RuntimeError(f"TTS-Anbieter {provider_id} nicht gefunden oder abgeschaltet")
    if not client.is_available():
        raise RuntimeError(f"TTS-Anbieter {provider_id} nicht erreichbar")
    return client
