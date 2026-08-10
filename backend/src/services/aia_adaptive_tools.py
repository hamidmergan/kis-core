"""Adaptive language level for the generated study tools.

The chat already pitches its answers at a learner's stored CEFR level
(:mod:`src.services.aia_adaptive_chat`). The study tools -- Lernkarten,
Karteikarten, Quiz, Lueckentext, Vokabeltest, Mindmap, Datentabelle -- did not:
they generated at a fixed register (Lernkarten even hardcoded "B1"), so an A1
learner and a C2 learner got the exact same cards and questions.

This module gives the tools the SAME treatment as the chat, but phrased for
generating material rather than answering a question: it turns the learner's
level plus an admin-editable behaviour text into a prompt appendix that steers
the WORDING of the generated items (questions, options, definitions, labels)
without touching their number, their JSON shape or which answer is correct.

Kept deliberately tiny and side-effect free (the ``adaptive_tool_appendix``
builder is pure and unit-testable). :func:`build_adaptive_tool_suffix` is the
one DB-backed convenience the Celery tasks call, so a task stays a one-liner.
"""

from src.services.aia_adaptive_chat import level_texts
from src.services.aia_level_ladder import resolve_prompt_setting

LEVEL_PLACEHOLDER = "{level}"
EXAMPLE_PLACEHOLDER = "{example}"
DESCRIPTION_PLACEHOLDER = "{description}"

# Admin-settings key for the tool behaviour text (German-scoped, "_de" suffix,
# like the diagnosis/chat settings). Separate from the chat's
# ``language_diagnosis_adaptive_behavior_de``: the chat text is written for
# ANSWERING ("keep the whole answer short"), which would wrongly shrink a set of
# N generated cards. An empty stored value always means "use the code default".
ADAPTIVE_TOOL_BEHAVIOR_SETTING = "language_diagnosis_adaptive_tool_behavior_de"

# Der Standard bis 2026-08, mit eigener Stufen-Liste (der dritten Kopie derselben
# Liste). Bleibt stehen, um ihn beim Lesen als "nicht gesetzt" zu erkennen. Nicht
# loeschen, siehe aia_level_ladder.resolve_prompt_setting.
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

# Shipped default so the tools adapt from day one, before any expert edits it.
# Written as an instruction to the model in English (like every other system
# prompt here); it does NOT set the output language, which stays the tool's own
# output language ({language}). The crucial extra over the chat version is the
# "DO NOT change the count / JSON / correct answer" guard: the tool prompts
# already dictate an exact item count and a strict JSON shape, and the level must
# only change the WORDING, never fight that structure.
#
# Die eigene A1/A2..C1/C2-Liste ist raus: wie eine Stufe aussieht, steht ab 2026-08
# in der Stufen-Leiter und kommt ueber {description} herein.
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
    """Build the tool prompt appendix and the applied level.

    Returns ``("", None)`` when there is nothing to apply: no stored level, or an
    empty behaviour text. Otherwise returns the behaviour text with ``{level}``,
    ``{example}`` and ``{description}`` substituted, prefixed by a blank line so
    it appends cleanly to a system prompt. Mirrors
    :func:`src.services.aia_adaptive_chat.adaptive_chat_appendix` exactly, so both
    paths behave the same and read the same to an admin.
    """
    if not level or not behavior or not behavior.strip():
        return "", None
    text = (
        behavior.strip()
        .replace(LEVEL_PLACEHOLDER, level)
        .replace(EXAMPLE_PLACEHOLDER, (example or "").strip())
        .replace(DESCRIPTION_PLACEHOLDER, (description or "").strip())
    )
    return "\n\n" + text, level


def build_adaptive_tool_suffix(user_id: int | None, workspace_id: int | None = None) -> str:
    """The suffix to append to a tool's system prompt for this learner.

    Reads the learner's stored CEFR level and the admin behaviour/example
    settings, and returns the ready-to-append string (``""`` when the learner has
    no level yet, so the tool keeps its shipped register). This is the single
    DB-backed entry point the Celery tasks use; the pure builder above stays
    testable without a database.

    ``workspace_id`` applies the same gate the chat uses: adaptive output is
    coupled to the Sprachtrainer being ON for that workspace. The CEFR level is
    stored globally per user, so without this check a learner would get
    level-pitched cards and mind maps in a workspace whose chat answers plainly.
    Omitted (None) keeps the ungated behaviour, which is what older queued tasks
    carry.

    The level read is short-circuited: with no level we return early and never
    touch the settings table, which is the common case.
    """
    if not user_id:
        return ""
    from src import database as db

    if workspace_id is not None and not db.is_language_training_active(workspace_id):
        return ""

    level = db.get_user_language_level(user_id)["language_level"]
    if not level:
        return ""
    # Second half of the same gate: the owner released the trainer, but this
    # learner switched it off for themselves, so their cards and mind maps stay
    # plain like their chat answers. Read after the level check so the common
    # case (no level at all) never touches the settings table.
    if workspace_id is not None:
        settings = db.get_aia_user_settings(workspace_id, user_id) or {}
        if not settings.get("language_training_active", False):
            return ""
    behavior = resolve_prompt_setting(
        db.get_setting(ADAPTIVE_TOOL_BEHAVIOR_SETTING, ""),
        _LEGACY_ADAPTIVE_TOOL_BEHAVIOR,
        DEFAULT_ADAPTIVE_TOOL_BEHAVIOR,
    )
    example, description = level_texts(level)
    suffix, _ = adaptive_tool_appendix(level, behavior, example, description)
    return suffix
