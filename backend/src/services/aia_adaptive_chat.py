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

# Hard guard, appended AFTER the (admin-editable) behaviour text and therefore the
# LAST thing the model reads before answering. Deliberately NOT part of
# DEFAULT_ADAPTIVE_BEHAVIOR: an admin editing the behaviour text must not be able to
# delete it, and putting it INSIDE the block did not work — it then competes with the
# block's own "a simplified answer is usually LONGER, never shorter" a few lines above
# and loses. Measured 2026-07-29: with the adaptive block on, "mein auto ist rot"
# produced a chatty invented answer with source chips; with the block off, the same
# question produced the correct one-sentence refusal. So the block, not the system
# prompt, is what overrides the refusal rule, and the counter-rule has to sit last and
# be about AUTHORITY (what the block may decide) rather than about length.
ADAPTIVE_SOURCES_GUARD = (
    "\n\nHIGHEST-PRIORITY RULE, IT OVERRIDES EVERYTHING ABOVE: any adaptation or style "
    "rules above only shape HOW you word an answer you are allowed to give. They NEVER "
    "decide WHETHER you answer, and 'never shorter' NEVER applies to a refusal. If the "
    "provided documents do not contain the answer, or the message is not an answerable "
    "question about them, then your ENTIRE reply is the single 'not in the provided "
    "sources' sentence from the system prompt, in the language of the message. Nothing "
    "before it, nothing after it: no restating the message, no explanation of why, no "
    "suggestions, no example questions, no encouragement, no offer to help. Never "
    "answer from your own knowledge instead, and that INCLUDES grammar, word forms, "
    "vocabulary and language rules that are not stated in the documents — being a "
    "language tutor does not make language knowledge a source.\n"
    "A QUOTE IS NOT COVERAGE. A message may quote a sentence that really does appear in "
    "the documents and still ask something the documents never state. Judge the ANSWER, "
    "not the quote.\n"
    "HOW TO DECIDE, IN THIS ORDER. (1) Look through the documents for a passage that "
    "STATES the rule, definition or fact the message asks for. (2) Found one: answer "
    "fully and normally from it, at the learner's level. (3) Found none: the refusal "
    "sentence alone. Never skip step 1, and never decide by TOPIC — no subject is "
    "forbidden and no subject is automatically allowed. Grammar is only forbidden as an "
    "answer YOU supply; a grammar rule a document spells out is ordinary source content "
    "and refusing it is just as wrong as inventing one.\n"
    "EXAMPLE A — REFUSE. The documents are lecture recordings and slides about writing a "
    "seminar paper. None of them teaches language rules. A message asks why a particular "
    "word in a quoted sentence takes one case rather than another. Step 1 finds nothing "
    "that states the rule, so the explanation would be your own language knowledge. "
    "Reply: the refusal sentence ALONE — no step-by-step, no table, no summary, however "
    "well sourced it might look.\n"
    "EXAMPLE B — ANSWER. Same question, but the documents now also include a grammar "
    "handout that states the rule. Step 1 finds it, so the answer IS in the sources. "
    "Explain it fully from that handout. Refusing here would be WRONG."
)


def example_for_level(level: str | None, examples: dict) -> str:
    """The calibration example string for a learner's own level.

    Every CEFR level now carries its own example. Several examples for a band are
    joined with ' / '. Empty when there is no level, or no example stored for it.
    """
    if not level:
        return ""
    return " / ".join(example_items(examples.get(level, "")))


def seal_adaptive_suffix(behavior_suffix: str, weakness_suffix: str = "") -> str:
    """Assemble the full user-message suffix, with the sources guard LAST.

    The whole suffix is appended at the END of the user message, so whatever sits
    last is what the model reads last — and that has to be the guard, not the
    behaviour text's "never shorter" or a weakness hint. Any further appendix must
    be passed in here rather than concatenated after the return value, otherwise it
    displaces the guard and the refusal regression comes back.

    The guard is appended even with NO adaptive block. It used to be skipped there
    ("the system prompt refuses on its own"), which is exactly what the screenshot
    of 2026-07-29 disproved: with the trainer off, the tutor invented a grammar
    lesson the sources never contained. The rule holds whether the Fachsprachentrainer
    is on or off, so the text goes out either way. The deterministic enforcement lives
    in ``aia_source_coverage`` — this is the second layer, not the only one.
    """
    return behavior_suffix + weakness_suffix + ADAPTIVE_SOURCES_GUARD


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
