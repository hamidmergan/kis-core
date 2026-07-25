"""Adaptive tutor behaviour for the existing workspace chat.

A learner who has a stored CEFR level should get answers pitched at that level.
The didactics live in an admin-editable setting with a shipped German default,
so a language expert can change how the tutor speaks to an A1 versus a B1 learner
without a code change. This helper turns (level, behaviour text) into a system
prompt appendix plus the level that was actually applied, so the caller can both
steer the model and report the level to an admin.

Deliberately tiny and side-effect free: chat.py stays lean, and this is unit
testable on its own.
"""

from src.services.aia_diagnosis_chat import example_items

LEVEL_PLACEHOLDER = "{level}"
EXAMPLE_PLACEHOLDER = "{example}"

# Shipped default so adaptive behaviour works from day one, before any expert
# touches it. Editable in the admin under the language-diagnosis tab. Written as
# an instruction to the model in English (like every other system prompt here);
# it does NOT set the answer language, which stays the learner's chat language.
DEFAULT_ADAPTIVE_BEHAVIOR = (
    "ADAPT TO THE LEARNER. The learner has language level {level}. This block "
    "OVERRIDES the length, completeness and terminology rules above whenever they "
    "conflict with it.\n"
    "Always address the learner with the informal second person (German \"du\"), "
    "never the formal \"Sie\", at every level.\n"
    "- A1 or A2: answer in VERY SIMPLE language. Short sentences, one idea per "
    "sentence, everyday words. Give only the few MOST important points, not "
    "everything. Explain every difficult or technical word right after it in "
    "simple words, or replace it with a simple word. Keep the whole answer short.\n"
    "- B1: you may give more detail and keep technical terms, but still explain "
    "each technical term briefly.\n"
    "- Above B1: answer normally, no simplification.\n"
    "Never change the facts, only the language, the length and the depth of "
    "explanation.\n"
    "An example of {level} language: {example}"
)


def example_for_level(level: str | None, examples: dict) -> str:
    """The calibration example string for a learner's own level.

    B1+ has no example of its own, so it borrows the B2 sample (a B2-quality
    answer is exactly what "above B1" sounds like). Several examples for a band
    are joined with ' / '. Empty when there is no level.
    """
    if not level:
        return ""
    key = "B2" if level == "B1+" else level
    return " / ".join(example_items(examples.get(key, "")))


def adaptive_chat_appendix(
    level: str | None, behavior: str, example: str = ""
) -> tuple[str, str | None]:
    """Build the system-prompt appendix and the applied level.

    Returns ``("", None)`` when there is nothing to apply: no stored level, or an
    empty behaviour text. Otherwise returns the behaviour text with the level and
    the example substituted, prefixed by a blank line so it appends cleanly.

    Placeholders work exactly like the diagnosis prompt: ``{level}`` becomes the
    learner's level and ``{example}`` becomes a calibration sample of that level
    (the same per-level examples the diagnosis uses). No auto-appending: if the
    text has no ``{example}`` placeholder, no example is added.
    """
    if not level or not behavior or not behavior.strip():
        return "", None
    text = (
        behavior.strip()
        .replace(LEVEL_PLACEHOLDER, level)
        .replace(EXAMPLE_PLACEHOLDER, (example or "").strip())
    )
    return "\n\n" + text, level
