"""Shared helpers for KI-Assistent Celery tasks."""

import re

from langfuse.decorators import langfuse_context

from src.features.ai_assistant.tasks._json_commas import drop_trailing_commas


def _format_ts(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


# The language the tools generate in when the course room says nothing else.
TOOL_OUTPUT_LANGUAGE = "German"


# Admin setting: the language of the four learning tools.
LEARNING_TOOLS_LANGUAGE_SETTING = "aia_learning_tools_language"

# The tools that follow this setting, everything else stays with the course room.
LEARNING_TOOLS: frozenset[str] = frozenset({"karteikarten", "quiz"})


def learning_tools_language() -> tuple[str, str]:
    """Language for flashcards, quiz, data table and mind map, set globally in the admin area."""
    from src.features.admin.repository.settings import get_setting
    from src.i18n import DEFAULT_LEARNING_TOOLS_LANGUAGE, TRANSCRIPT_LANGUAGES

    code = get_setting(LEARNING_TOOLS_LANGUAGE_SETTING, DEFAULT_LEARNING_TOOLS_LANGUAGE)
    if code not in TRANSCRIPT_LANGUAGES:
        # A value nobody offers any more, otherwise the code would end up in the prompt.
        code = DEFAULT_LEARNING_TOOLS_LANGUAGE
    return code, TRANSCRIPT_LANGUAGES[code]["name"]


def tool_output_language(workspace_id) -> tuple[str, str]:
    """Language of this course room's language trainer content, not the interface language."""
    from src.i18n import DEFAULT_DIAGNOSIS_LANGUAGE, TRANSCRIPT_LANGUAGES

    code = DEFAULT_DIAGNOSIS_LANGUAGE
    if workspace_id:
        from src import database as db
        try:
            workspace = db.get_aia_workspace_by_id(workspace_id) or {}
            code = workspace.get("diagnosis_language") or DEFAULT_DIAGNOSIS_LANGUAGE
        except Exception:  # noqa: BLE001 - der Standard ist eine brauchbare Antwort
            pass
    if code not in TRANSCRIPT_LANGUAGES:
        # Then the code falls back too, otherwise the rule sits under a dead key.
        code = DEFAULT_DIAGNOSIS_LANGUAGE
    return code, TRANSCRIPT_LANGUAGES[code]["name"]


def _get_llm_client():
    """Return (client, model, provider) using the configured LLM provider."""
    from langfuse.openai import OpenAI
    from src.dependencies import _binding_tuple, _resolve_llm_binding
    from src.services import provider_transport
    binding = _resolve_llm_binding()
    _api_key, _base_url, _model, _provider = _binding_tuple(binding)
    from src.features.ai_assistant.tasks._retry import RetryingClient
    # max_retries=0 stays, RetryingClient makes the distinction.
    client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=120,
                    http_client=provider_transport.sdk_http_client(binding))
    langfuse_context.update_current_observation(
        metadata={"provider": _provider, "base_url": _base_url, "model": _model},
    )
    return RetryingClient(client), _model, _provider


def _clean_llm_json(text: str) -> str:
    """Strip markdown fences, whitespace and trailing commas from LLM JSON output."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)
    # In load run 15 gemma left a comma after the last option and two quizzes failed on it.
    return drop_trailing_commas(text.strip())
