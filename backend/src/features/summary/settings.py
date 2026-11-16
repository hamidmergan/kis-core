"""The operating numbers of this pipeline, named so the code reads like prose.

The numbers themselves, their ranges and their rights live in services/tool_numbers.py
together with those of every other tool. This module only gives them their names here.
"""

from src.services.tool_numbers import value_of

TOOL = "summary"


def call_timeout() -> int:
    """Seconds a single model call may take before we drop it ourselves."""
    return value_of("summary_call_timeout_seconds")
