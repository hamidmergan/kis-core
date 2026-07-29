"""Grammatik-Übung aus Quelltext (tool='grammatik', mode='source').

Ein Generier-Call liefert das Musterpaar und N Satzpaare. Der Aufgabentyp steuert
den Call nur über zwei Textfelder aus dem Katalog (``instruction`` und ``rule``),
deshalb kostet ein neuer Aufgabentyp hier keine Zeile Code.

Wichtig für den Zweck des Tools: die Sätze werden NEU aus dem Quellinhalt gebaut,
nicht aus einem Arbeitsblatt übernommen. Deshalb funktioniert das Tool mit jeder
Quelle, auch mit einem Mathe-Skript.
"""

import json

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json, _language_label

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.services.aia_grammar_check import normalize
from src.services.aia_grammar_types import example_pair, localized


_SHAPE = (
    'Respond ONLY with a JSON object:\n'
    '{"title": "Short topic title", '
    '"example": {"before": "Example sentence in the original form", '
    '"after": "The same sentence transformed"}, '
    '"exercises": [{"before": "Sentence the learner transforms", '
    '"after": "The expected transformed sentence", '
    '"explanation": "One short sentence naming the form that changed"}]}\n'
)

# Fragezeichen quer über Schriftsysteme. Ein 'before' mit Fragezeichen ist keine
# Aussage und damit nicht umformbar, egal in welcher Sprache.
_QUESTION_MARKS = "?？؟;՞।"

# Unter dieser Quote gilt ein Durchlauf als misslungen: lieber ein fehlgeschlagenes
# Set als eine Übung, in der die Hälfte der Aufgaben unlösbar ist.
_MIN_USABLE_RATIO = 0.5


def generate_grammar_from_source(
    client, model,
    ctx: QuelleContext,
    grammar_type: dict,
    count: int,
    locale: str = "de",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
) -> tuple[list[dict], str, dict]:
    """Returns (items, title, header). ``header`` holds instruction + example pair.

    Empty items mean the run is unusable and the caller fails the set.
    """
    language = _language_label(locale)
    instruction = localized(grammar_type, "instruction", locale)
    target_form = localized(grammar_type, "label", locale)
    shipped_example = example_pair(grammar_type, locale)
    prompt = (
        _build_prompt(grammar_type, target_form, shipped_example, count, language)
        + adaptive_suffix + title_avoidance + coverage
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Write the output in {language}.\n\nSources:\n\n{ctx.context}"},
    ]
    # Same temperature as the MC tools: enough wording variety, still JSON-safe. The real
    # variation across runs comes from the rotating page subset in build_source_context.
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.6)
    data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))

    exercises = list(data.get("exercises") or [])[:count]
    items, claims = _build_items(exercises)

    # The model likes to slip back into comprehension questions ("Was bedeutet X?"),
    # which cannot be transformed and leave the learner stuck. Too many of those and
    # the whole run is thrown away rather than shipped half broken.
    wanted = min(count, len(exercises)) or count
    if len(items) < max(1, int(wanted * _MIN_USABLE_RATIO)):
        logger.warning(
            "KI Tutor: grammar run discarded, only {}/{} sentences were usable",
            len(items), wanted,
        )
        return [], "", {}

    example = data.get("example") or {}
    pattern_front = (example.get("before") or "").strip()
    pattern_back = (example.get("after") or "").strip()
    # No usable example from the model? Show the catalogue's own worked pair, so the
    # learner is never left without one.
    if not pattern_front or not pattern_back:
        pattern_front, pattern_back = shipped_example["before"], shipped_example["after"]
    header = {
        "instruction": instruction,
        "pattern_front": pattern_front,
        "pattern_back": pattern_back,
    }

    # Same post-hoc attribution as every other tool: the chip points at the page the
    # sentence's content came from, nav-only. A grammar sentence is a rewrite of one
    # passage, so multi=False (one origin, not every page mentioning the words).
    attach_chips(items, claims, ctx, multi=False)

    title = (data.get("title") or "").strip() or localized(grammar_type, "label", locale)
    return items, title, header


def _build_prompt(grammar_type: dict, target_form: str, example: dict,
                  count: int, language: str) -> str:
    # The worked pair is given as a SHAPE TO COPY, not only as a rule. Rules alone
    # get ignored by the chat model, which then falls back to what it does most
    # often and returns comprehension questions instead of transformable sentences.
    shape = (
        "SHAPE TO COPY. Every exercise looks exactly like this pair:\n"
        f'  before: "{example["before"]}"\n'
        f'  after:  "{example["after"]}"\n\n'
        "NOT like these, they are all wrong here:\n"
        '  "Was bedeutet wissenschaftliches Arbeiten?"  (a question, cannot be transformed)\n'
        '  "Nennen Sie drei Beispiele."                 (an instruction, not a statement)\n'
        '  "Wissenschaftliches Arbeiten"                (not a sentence)\n\n'
    )
    return (
        f"You build a grammar drill from the given source text. "
        f"Write ALL sentences in {language}, regardless of the source-text language.\n\n"
        # The learner-facing instruction is deliberately NOT sent: it only says "follow
        # the pattern below" and names no form. The catalogue label does.
        f"Target form: {target_form}\n"
        f"Transformation rule: {grammar_type['rule']}\n\n"
        + shape +
        "How to build the sentences:\n"
        "- Take the FACTS, terms and topics from the source text and write NEW, simple "
        "sentences about them. Never copy a sentence from the source verbatim.\n"
        "- Never copy exercises that may already be in the source text. The source supplies "
        "subject matter, not exercises.\n"
        "- Every 'before' is a STATEMENT. Never a question, never an instruction to the "
        "learner, never a bare phrase.\n"
        "- Every 'before' MUST be a valid input for the transformation rule above. "
        "If the rule needs a modal verb, every sentence contains one.\n"
        "- 'after' is the single expected solution, correct and complete, and it must "
        "differ from 'before'.\n"
        # Deliberately NO length or complexity rule here. How hard a sentence is comes
        # from exactly one place, the learner's CEFR level (build_adaptive_tool_suffix).
        # A cap here would contradict that block at B2 and above, where it says not to
        # simplify. This line is only about shape: one sentence, not a paragraph.
        "- Every 'before' and every 'after' is exactly ONE sentence.\n"
        "- Do NOT use personal names. Write 'die Dozentin', 'das Team', 'according to the source' "
        "instead, matching the output language.\n"
        "- 'example' is the worked pair shown above the exercises. It follows the same rule "
        "but must NOT repeat any of the exercise sentences.\n\n"
        + _SHAPE +
        f"Create exactly {count} exercises."
    )


def is_usable_pair(before: str, after: str) -> bool:
    """Whether a generated pair is actually solvable by a learner.

    Deliberately language-agnostic: no word lists, only shape. A question or an
    unchanged sentence has no correct transformation, so shipping it would leave
    the learner with an exercise nobody can answer.
    """
    if not before or not after:
        return False
    if before[-1] in _QUESTION_MARKS or after[-1] in _QUESTION_MARKS:
        return False
    if normalize(before) == normalize(after):
        return False
    # A single word (or none) is a heading, not a sentence to transform.
    return len(before.split()) >= 3


def _build_items(exercises: list[dict]) -> tuple[list[dict], list[str]]:
    """Item rows + the claim text used for source attribution.

    ``options``/``correct_idx`` stay unset: the answer is free text, checked later
    against ``back`` (see services/aia_grammar_check.py).
    """
    items, claims = [], []
    for ex in exercises:
        before = (ex.get("before") or "").strip()
        after = (ex.get("after") or "").strip()
        if not is_usable_pair(before, after):
            logger.debug("KI Tutor: grammar pair dropped: {!r} -> {!r}", before, after)
            continue
        items.append({
            "front": before,
            "back": after,
            "explanation": (ex.get("explanation") or "").strip() or None,
            # Which numbered context section the model says it used. Not persisted
            # (finalize_exercise_set only reads known keys), it exists so the caller
            # can check that every section was actually served.
            "_section": ex.get("section"),
        })
        # The transformed sentence carries the content, so it is what gets attributed.
        claims.append(after)
    return items, claims
