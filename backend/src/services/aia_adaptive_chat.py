"""Turns level and behaviour text into the suffix for the chat prompt."""

from src.services.aia_diagnosis_chat import (
    LEVEL_EXAMPLES_SETTING,
    example_items,
    parse_level_examples,
)
from src.services.aia_level_ladder import (
    LEVEL_DESCRIPTIONS_SETTING,
    description_for_level,
    parse_level_descriptions,
)

LEVEL_PLACEHOLDER = "{level}"
EXAMPLE_PLACEHOLDER = "{example}"
DESCRIPTION_PLACEHOLDER = "{description}"

# The old default text, kept only to recognise it as 'not set' on read.
_LEGACY_ADAPTIVE_BEHAVIOR = (
    "WRITING STYLE. Write at CEFR level {level}. This is a STYLE rule and nothing "
    "else: it changes the WORDING of an answer you are already allowed to give. It "
    "gives you no role, no task and no permission of its own. It never decides "
    "WHETHER you answer, never adds a topic you may cover, and never overrides the "
    "RESPONSE STRUCTURE rules above: keep the headings, the bullets and the tables "
    "at every level.\n"
    "Always use the informal second person (German \"du\"), never the formal "
    "\"Sie\", at every level.\n"
    "- A1 or A2: very simple language. Short sentences, one idea per sentence, "
    "everyday words. Where a technical term FROM THE DOCUMENTS has to appear, add a "
    "short plain-language gloss right after it, or use a simpler word instead.\n"
    "- B1: more detail is fine and technical terms may stay, with a brief gloss.\n"
    "- B2: normal wording, in full. Technical terms where they fit, gloss only the "
    "less common ones. No deliberate simplification.\n"
    "- C1 or C2: full depth, precise wording, idiomatic phrasing and technical "
    "terms as an expert would use them. Do not simplify and do not gloss ordinary "
    "technical vocabulary.\n"
    "SIMPLER NEVER MEANS LESS. Cover exactly the same facts, dates, times, "
    "numbers, names and steps you would give at the highest level. Never leave a "
    "fact out, never merge two facts into one, and never water a fact down to "
    "make the answer easier. Simplifying splits one hard sentence into several "
    "easy ones, so a simplified answer is usually LONGER than the unsimplified "
    "one, never shorter. This applies ONLY to an answer you are allowed to give. It "
    "NEVER applies to the not-in-sources sentence, which stays exactly one sentence "
    "at every level.\n"
    "THIS STYLE RULE IS NOT A SUBJECT. It says how to write, never what to write "
    "about. It does NOT make you a language teacher and it does NOT put grammar, "
    "word forms, cases, tenses or vocabulary rules into your remit. If a message "
    "asks you to explain such a rule and no document states it, the reply is the "
    "not-in-sources sentence, exactly as it would be without this style rule. A "
    "message that quotes words which do appear in the documents is still such a "
    "message: the quoted words are not the answer.\n"
    "An example of {level} wording: {example}"
)

# Shipped default text, changeable by the admin under the language diagnosis.
DEFAULT_ADAPTIVE_BEHAVIOR = (
    "WRITING STYLE. Write at CEFR level {level}. This is a STYLE rule and nothing "
    "else: it changes the WORDING of an answer you are already allowed to give. It "
    "gives you no role, no task and no permission of its own. It never decides "
    "WHETHER you answer, never adds a topic you may cover, and never overrides the "
    "RESPONSE STRUCTURE rules above: keep the headings, the bullets and the tables "
    "at every level.\n"
    "Always use the informal second person (German \"du\"), never the formal "
    "\"Sie\", at every level.\n"
    "A learner at {level} writes like this: {description}\n"
    "Pitch your wording so that such a learner reads it easily. Where a technical "
    "term FROM THE DOCUMENTS has to appear, add a short plain-language gloss right "
    "after it, or use a simpler word instead. The higher the level, the less you "
    "gloss and the less you simplify: at B2 gloss only the less common terms, and "
    "at C1 or C2 do not simplify and do not gloss ordinary technical vocabulary.\n"
    "SIMPLER NEVER MEANS LESS. Cover exactly the same facts, dates, times, "
    "numbers, names and steps you would give at the highest level. Never leave a "
    "fact out, never merge two facts into one, and never water a fact down to "
    "make the answer easier. Simplifying splits one hard sentence into several "
    "easy ones, so a simplified answer is usually LONGER than the unsimplified "
    "one, never shorter. This applies ONLY to an answer you are allowed to give. It "
    "NEVER applies to the not-in-sources sentence, which stays exactly one sentence "
    "at every level.\n"
    # The addition about quoted words is gone, it also hit ordinary word questions.
    "THIS STYLE RULE IS NOT A SUBJECT. It says how to write, never what to write "
    "about. It does NOT make you a language teacher and it does NOT put grammar, "
    "word forms, cases, tenses or vocabulary rules into your remit. If a message "
    "asks you to explain such a rule and no document states it, the reply is the "
    "not-in-sources sentence, exactly as it would be without this style rule.\n"
    "An example of {level} wording: {example}"
)

# Stands LAST because inside the behaviour text it lost against its own rules.
ADAPTIVE_SOURCES_GUARD = (
    "\n\nHIGHEST-PRIORITY RULE, IT OVERRIDES EVERYTHING ABOVE: the style rules above "
    "only shape HOW you word an answer you are allowed to give. They NEVER decide "
    "WHETHER you answer, and 'never shorter' NEVER applies to a refusal. Whether the "
    "documents answer the question, and the shape of your reply when they do not, is "
    "decided by the system prompt alone.\n"
    "Never answer from your own knowledge, and that INCLUDES grammar, word forms, "
    "vocabulary and language rules that are not stated in the documents. Being a language "
    "tutor does not make language knowledge a source.\n"
    "A QUOTE IS NOT COVERAGE. A message may quote a sentence that really does appear in "
    "the documents and still ask something the documents never state. Judge the ANSWER, "
    "not the quote.\n"
    "DECIDE BY PASSAGE, NEVER BY TOPIC. No subject is forbidden and no subject is "
    "automatically allowed: grammar is only forbidden as an answer YOU supply, while a "
    "grammar rule a document spells out is ordinary source content, and refusing it is "
    "just as wrong as inventing one."
)


def example_for_level(level: str | None, examples: dict) -> str:
    """The example sentence for a learner's level, empty when none is stored."""
    if not level:
        return ""
    return " / ".join(example_items(examples.get(level, "")))


def seal_adaptive_suffix(behavior_suffix: str) -> str:
    """Appends the guard behind the trainer block, and only then."""
    if not behavior_suffix:
        return ""
    return behavior_suffix + ADAPTIVE_SOURCES_GUARD


def adaptive_chat_appendix(
    level: str | None, behavior: str, example: str = "", description: str = ""
) -> tuple[str, str | None]:
    """Inserts level, example and description into the behaviour text."""
    if not level or not behavior or not behavior.strip():
        return "", None
    text = (
        behavior.strip()
        .replace(LEVEL_PLACEHOLDER, level)
        .replace(EXAMPLE_PLACEHOLDER, (example or "").strip())
        .replace(DESCRIPTION_PLACEHOLDER, (description or "").strip())
    )
    return "\n\n" + text, level


def level_texts(level: str | None) -> tuple[str, str]:
    """Example sentence and description of the level, from the settings."""
    if not level:
        return "", ""
    from src import database as db

    example = example_for_level(
        level, parse_level_examples(db.get_setting(LEVEL_EXAMPLES_SETTING, ""))
    )
    description = description_for_level(
        level, parse_level_descriptions(db.get_setting(LEVEL_DESCRIPTIONS_SETTING, ""))
    )
    return example, description
