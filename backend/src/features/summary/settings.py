"""The operating numbers of this pipeline, named so the code reads like prose.

The numbers themselves, their ranges and their rights live in services/tool_numbers.py
together with those of every other tool. This module only gives them their names here.
"""

from src.services.tool_numbers import value_of

TOOL = "summary"


def facts_cap() -> int:
    """Facts one read call may return."""
    return value_of("summary_read_max_facts")


def call_timeout() -> int:
    """Seconds a single model call may take before we drop it ourselves."""
    return value_of("summary_call_timeout_seconds")


def output_tokens_cap() -> int:
    """Tokens a read call may answer with, the guard against a cut off JSON structure."""
    return value_of("summary_max_output_tokens")
