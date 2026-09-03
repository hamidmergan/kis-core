"""Tunes the generated learning tools to the learner's language level."""

from src.services.aia_adaptive_chat import level_texts
from src.services.aia_level_ladder import resolve_prompt_setting

LEVEL_PLACEHOLDER = "{level}"
EXAMPLE_PLACEHOLDER = "{example}"
DESCRIPTION_PLACEHOLDER = "{description}"

# A separate admin key for the tool text, apart from the chat text.
ADAPTIVE_TOOL_BEHAVIOR_SETTING = "language_diagnosis_adaptive_tool_behavior_de"

# The old default stays so it is recognised on read.
_LEGACY_ADAPTIVE_TOOL_BEHAVIOR = (
    "ADAPT THE LANGUAGE TO THE LEARNER. This study material is generated for a "
    "learner whose language level is {level}. This block OVERRIDES any wording or "
    "difficulty rule above whenever they conflict with it.\n"
    "Write every part the learner reads -- questions, answer options, "
    "definitions, explanations, labels, gap sentences -- so a {level} learner "
    "understands it easily. Address the learner with the informal second person "
    "(German \"du\"), never the formal \"Sie\".\n"
    "- A1 or A2: use VERY SIMPLE language. Short sentences, one idea each, "
    "everyday words. Explain or replace every difficult or technical word right "
    "where it appears.\n"
    "- B1: you may keep technical terms, but explain each one briefly in simple "
    "words.\n"
    "- B2: write normally. Use technical terms where they fit and only gloss the "
    "less common ones. No deliberate simplification.\n"
    "- C1 or C2: use precise, idiomatic wording and technical terms as an expert "
    "would. Do not simplify and do not gloss ordinary technical vocabulary.\n"
    "DO NOT change the requested number of items, the JSON structure, the number "
    "of answer options, or which answer is correct. Change ONLY the wording and "
    "how much you explain, never the facts and never the format.\n"
    "An example of {level} language: {example}"
)

# Shipped default, it only changes the wording and never count or solution.
DEFAULT_ADAPTIVE_TOOL_BEHAVIOR = (
    "ADAPT THE LANGUAGE TO THE LEARNER. This study material is generated for a "
    "learner whose language level is {level}. This block OVERRIDES any wording or "
    "difficulty rule above whenever they conflict with it.\n"
    "Write every part the learner reads -- questions, answer options, "
    "definitions, explanations, labels, gap sentences -- so a {level} learner "
    "understands it easily. Address the learner with the informal second person "
    "(German \"du\"), never the formal \"Sie\".\n"
    "A learner at {level} writes like this: {description}\n"
    "Where a difficult or technical word has to appear, explain or replace it "
    "right where it appears. The higher the level, the less you gloss and the "
    "less you simplify: at B2 gloss only the less common terms, and at C1 or C2 "
    "do not simplify and do not gloss ordinary technical vocabulary.\n"
    "DO NOT change the requested number of items, the JSON structure, the number "
    "of answer options, or which answer is correct. Change ONLY the wording and "
    "how much you explain, never the facts and never the format.\n"
    "An example of {level} language: {example}"
)


def adaptive_tool_appendix(
    level: str | None, behavior: str, example: str = "", description: str = ""
) -> tuple[str, str | None]:
    """Builds the prompt suffix and names the applied level."""
    if not level or not behavior or not behavior.strip():
        return "", None
    text = (
        behavior.strip()
        .replace(LEVEL_PLACEHOLDER, level)
        .replace(EXAMPLE_PLACEHOLDER, (example or "").strip())
        .replace(DESCRIPTION_PLACEHOLDER, (description or "").strip())
    )
    return "\n\n" + text, level


def build_adaptive_tool_suffix(user_id: int | None) -> str:
    """The suffix for this learner, gated on the person's switch and level."""
    if not user_id:
        return ""
    from src import database as db

    if not db.is_language_training_ready(user_id):
        return ""
    level = db.get_user_language_level(user_id)["language_level"]
    if not level:
        return ""
    behavior = resolve_prompt_setting(
        db.get_setting(ADAPTIVE_TOOL_BEHAVIOR_SETTING, ""),
        _LEGACY_ADAPTIVE_TOOL_BEHAVIOR,
        DEFAULT_ADAPTIVE_TOOL_BEHAVIOR,
    )
    example, description = level_texts(level)
    suffix, _ = adaptive_tool_appendix(level, behavior, example, description)
    return suffix
