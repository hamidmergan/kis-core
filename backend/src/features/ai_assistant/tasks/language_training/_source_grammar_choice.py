"""Grammatik-Quiz aus Quelltext (tool='grammatik', Aufgabentyp mit format='choice').

Läuft wie das Quiz, prüft aber die Form statt den Inhalt: Aufgabenzeile, ein Satz,
vier Optionen. Angelegt wurde es, weil das inhaltliche Quiz auf einem Grammatik-
Arbeitsblatt Fragen zum Inhalt stellt ("Welche Gerichte wurden gekocht?") und die
Form gar nicht vorkommt.

Die Aufgabenzeile steht in jedem Item und nicht einmal über dem Set: welche Formen
drankommen, entscheidet das Modell am Quelltext, ein Set mischt also mehrere.

Wie beim Freitext-Generator werden die Sätze NEU aus dem Quellinhalt gebaut, nie aus
einem Arbeitsblatt übernommen. Deshalb funktioniert das Werkzeug mit jeder Quelle.
"""

import json

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json, _language_label

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.services.aia_grammar_check import normalize, overlap_ratio
from src.services.aia_grammar_types import (
    example_pair, localized, worked_exercises, wrong_forms,
)


_SHAPE = (
    'Respond ONLY with a JSON object:\n'
    '{"title": "Short topic title", '
    '"exercises": [{"task": "The form the learner has to produce", '
    '"sentence": "The statement to transform", '
    '"options": ["...", "...", "...", "..."], '
    '"correct_idx": 0, '
    '"explanation": "One short sentence naming the form that decides it"}]}\n'
)

# Vier Optionen, wie im Quiz. Weniger sieht nach einem Fehler aus, mehr passt nicht
# mehr auf die Karte.
_OPTION_COUNT = 4

# Ab dieser Wortüberdeckung mit der Lösung gilt eine falsche Option als Formvariante
# und nicht als andere Aussage. Das ist der eigentliche Inhalt-gegen-Form-Filter:
# vier Passiv-Varianten teilen fast alle Wörter, vier verschiedene Gerichte teilen
# nur das "und". Kommt ohne Wortlisten aus und gilt damit für jede Sprache.
_MIN_OPTION_OVERLAP = 0.5

# Weniger Aufgaben lohnen das Öffnen nicht, dann lieber ein fehlgeschlagenes Set. Mehr
# zu verlangen wäre falsch: die Filter entscheiden pro Aufgabe, was durchkommt ist gut,
# ein kurzes Set ist also kurz und nicht schlecht.
_MIN_ITEMS = 3

# Ein Nachschlag, nicht mehr. Das Anbieter-Limit ist hochschulweit geteilt, und wenn
# zwei Würfe hintereinander unbrauchbar sind, hilft ein dritter erfahrungsgemäss auch
# nicht mehr.
_MAX_ATTEMPTS = 2


def generate_grammar_choice_from_source(
    client, model,
    ctx: QuelleContext,
    grammar_type: dict,
    count: int,
    locale: str = "de",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
) -> tuple[list[dict], str, dict]:
    """Returns (items, title, header). ``header`` is always empty for ticking sets.

    Empty items mean the run is unusable and the caller fails the set.
    """
    language = _language_label(locale)
    prompt = (
        _build_prompt(grammar_type, count, language, locale)
        + adaptive_suffix + title_avoidance + coverage
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": (
            f"Write the output in {language}.\n\nSources:\n\n{ctx.context}"
            + _reminder(grammar_type, locale, count)
        )},
    ]
    banned = _example_texts(grammar_type, locale)

    # Measured against the live model: it wastes part of every draw on lecture material,
    # sometimes all of it (ten exercises, the same string in all four slots). So a short
    # draw is topped up by a second one and BOTH are kept, rather than the first being
    # thrown away. One top-up only, the provider limit is shared across the university.
    items: list[dict] = []
    claims: list[str] = []
    data: dict = {}
    seen: set = set()
    for attempt in range(_MAX_ATTEMPTS):
        fresh, fresh_claims, data = _one_draw(client, model, messages, count, banned)
        for item, claim in zip(fresh, fresh_claims):
            key = normalize(item["front"])
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
            claims.append(claim)
        if len(items) >= count:
            break
        logger.info(
            "KI Tutor: grammar quiz draw {} gave {}/{} exercises",
            attempt + 1, len(items), count,
        )
    items, claims = items[:count], claims[:count]

    # Below this a set is too thin to be worth opening. Above it a short set is short,
    # not bad: every exercise that got here passed the per-item filters.
    if len(items) < min(count, _MIN_ITEMS):
        logger.warning(
            "KI Tutor: grammar quiz discarded, only {} usable exercises after {} draws",
            len(items), _MAX_ATTEMPTS,
        )
        return [], "", {}

    # Same post-hoc attribution as every other tool: the chip points at the page the
    # sentence's content came from, nav-only. multi=False, one sentence has one origin.
    attach_chips(items, claims, ctx, multi=False)

    title = (data.get("title") or "").strip() or localized(grammar_type, "label", locale)
    # No set-level instruction or worked pair: every item carries its own task line.
    return items, title, {}


def _reminder(grammar_type: dict, locale: str, count: int) -> str:
    """Three finished exercises, AFTER the material.

    This is not decoration, it decides whether the tool works at all. Measured on a
    lecture transcript: with the example only in the system prompt the model returned
    ten exercises whose four options were the same string, so every one was dropped and
    the set failed. Moving it behind the sources lifted that to 2 of 10, showing three
    worked exercises instead of one to 4 and 7 of 10.

    The reason a grammar handout hid the problem: that material shows dozens of form
    variants itself and the model copies them. Any other source shows none, so the
    examples have to carry the whole pattern.
    """
    blocks = []
    for i, ex in enumerate(worked_exercises(grammar_type, locale), start=1):
        options = " | ".join(f'"{opt}"' for opt in ex["options"])
        blocks.append(
            f'{i}. task: "{ex["task"]}"  sentence: "{ex["sentence"]}"\n'
            f"   options: {options}"
        )
    return (
        "\n\nREMINDER. Finished exercises, note that every options block holds FOUR "
        "DIFFERENT strings, never one sentence repeated:\n\n"
        + "\n".join(blocks)
        + f"\n\nNow write exactly {count} exercises about the sources above, in that "
        "shape, each about the subject matter of the sources and never about the "
        "reminder itself."
    )


def _one_draw(client, model, messages, count: int, banned: set):
    """One generation call, parsed and filtered. Returns (items, claims, data)."""
    # Same temperature as the other tools: enough wording variety, still JSON-safe.
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.6)
    data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
    exercises = list(data.get("exercises") or [])[:count]
    items, claims = _build_items(exercises, banned)
    return items, claims, data


def _build_prompt(grammar_type: dict, count: int, language: str, locale: str) -> str:
    # A finished exercise as a SHAPE TO COPY, not only as a rule. Rules alone get
    # ignored by the chat model, which then falls back to what it does most often
    # and returns content questions (same lesson as the overview prose fix).
    example = example_pair(grammar_type, locale)
    wrong = wrong_forms(grammar_type, locale)
    task_line = localized(grammar_type, "example_task", locale)
    options = "\n".join(
        f'    "{text}"{"   <- the correct one" if i == 0 else ""}'
        for i, text in enumerate([example["after"], *wrong])
    )
    shape = (
        "SHAPE TO COPY. Every exercise looks exactly like this:\n"
        f'  task:     "{task_line}"\n'
        f'  sentence: "{example["before"]}"\n'
        "  options:\n"
        f"{options}\n\n"
        "NOT like this, these are the two mistakes to avoid:\n"
        '  task:     "Which dishes were cooked on Saturday evening?"\n'
        '  options:  "Pizza and pasta" / "Tacos and fajitas" / "Sushi and tempura"\n'
        "  That is a content question. The learner picks a fact, not a form.\n"
        f'  options:  "{example["after"]}"\n'
        f'            "{example["after"]}"\n'
        f'            "{example["after"]}"\n'
        f'            "{example["after"]}"\n'
        "  That is the same sentence four times. There is nothing left to choose.\n\n"
    )
    return (
        f"You build a grammar quiz from the given source text. "
        f"Write ALL tasks, sentences and options in {language}, regardless of the "
        f"source-text language.\n\n"
        f"What an exercise is: {grammar_type['rule']}\n\n"
        + shape +
        "Hard rules for the options:\n"
        "- Exactly four options, all four different from each other. Never write the "
        "same option twice.\n"
        "- All four differ only in FORM: same words, same content, only the "
        "grammatical form changes (auxiliary, participle, tense, case, ending, word "
        "order).\n"
        "- Exactly one option is correct. The other three are wrong answers to the "
        "task, each wrong for a different reason, and each one is a form a learner "
        "actually gets wrong.\n"
        "- None of the options repeats the sentence itself. The task always asks for "
        "a form the sentence is NOT in yet, so the answer always differs from it.\n"
        "- Never build options that differ in content, in facts, in numbers or in "
        "named things. That is a content question and belongs in the quiz tool.\n"
        "- 'correct_idx' is the position of the correct option, counting from 0.\n\n"
        "How to build the sentences:\n"
        "- Take the FACTS, terms and topics from the source text and write NEW, simple "
        "sentences about them. Never copy a sentence from the source verbatim.\n"
        "- The worked example above is only a shape. Never reuse its sentence, its "
        "options or its subject matter, they come from a different text.\n"
        "- 'task' asks for the required form and the sentence is NOT in that form yet. "
        "A sentence that already shows the target form has nothing left to transform.\n"
        "- Never copy exercises that may already be in the source text. The source "
        "supplies subject matter, not exercises.\n"
        "- Every 'sentence' is a STATEMENT and exactly ONE sentence. Never a question, "
        "never an instruction to the learner, never a bare phrase.\n"
        "- 'task' names the form to produce and nothing else. It never gives the answer "
        "away and never repeats the sentence.\n"
        # Deliberately NO length or complexity rule here. How hard a sentence is comes
        # from exactly one place, the learner's CEFR level (build_adaptive_tool_suffix).
        "- Do NOT use personal names. Write 'die Dozentin', 'das Team', 'according to "
        "the source' instead, matching the output language.\n\n"
        + _SHAPE +
        f"Create exactly {count} exercises."
    )


def _example_texts(grammar_type: dict, locale: str) -> set:
    """Normalised forms of every worked exercise, so a copy of one can be recognised.

    The model does ship them back as its own exercises, and a sentence from the shape
    has nothing to do with the learner's source.
    """
    texts = []
    for ex in worked_exercises(grammar_type, locale):
        texts.append(ex["sentence"])
        texts.extend(ex["options"])
    return {normalize(text) for text in texts if text}


def is_usable_choice(task: str, sentence: str, options: list, correct_idx) -> bool:
    """Whether a generated exercise actually drills a grammatical form.

    Deliberately language-agnostic: no word lists, only shape and word overlap. The
    overlap rule is what separates a form exercise from a content question, which is
    the failure this tool was built to fix.
    """
    if not task or not sentence:
        return False
    # A single word (or two) is a heading, not a sentence to transform.
    if len(sentence.split()) < 3:
        return False
    if not options or len(options) != _OPTION_COUNT:
        return False
    # bool is an int in Python, and True would silently mean index 1.
    if not isinstance(correct_idx, int) or isinstance(correct_idx, bool):
        return False
    if not 0 <= correct_idx < len(options):
        return False

    normalized = [normalize(opt) for opt in options]
    if not all(normalized):
        return False
    # Two options that only differ in case or punctuation are the same answer twice,
    # so the learner can be right and marked wrong.
    if len(set(normalized)) != len(normalized):
        return False
    # An option that repeats the given sentence transforms nothing. As the marked
    # solution it teaches nothing, as a distractor it only confuses. Same rule the
    # free-text drill applies to an unchanged solution.
    if normalize(sentence) in normalized:
        return False

    correct = options[correct_idx]
    return all(
        overlap_ratio(opt, correct) >= _MIN_OPTION_OVERLAP
        for i, opt in enumerate(options) if i != correct_idx
    )


def _build_items(exercises: list[dict], banned: set) -> tuple[list[dict], list[str]]:
    """Item rows + the claim text used for source attribution.

    ``front`` carries the task line in bold followed by the sentence, so the existing
    multiple-choice view renders it without a special case. ``banned`` holds the
    normalised worked example, which must never come back as an exercise.
    """
    items, claims = [], []
    for ex in exercises:
        task = (ex.get("task") or "").strip()
        sentence = (ex.get("sentence") or "").strip()
        options = [str(opt).strip() for opt in (ex.get("options") or [])]
        idx = ex.get("correct_idx")
        if not is_usable_choice(task, sentence, options, idx):
            logger.debug("KI Tutor: grammar quiz item dropped: {!r} {!r}", task, options)
            continue
        if normalize(sentence) in banned:
            logger.debug("KI Tutor: grammar quiz item dropped, copies the example: {!r}", sentence)
            continue
        correct = options[idx]
        items.append({
            # Blank line between the instruction and the sentence: run together on one
            # line it is not clear which sentence the task refers to. The view renders
            # the break, older sets without one are unaffected.
            "front": f"**{task}**\n\n{sentence}",
            "back": correct,
            "options": options,
            "correct_idx": idx,
            "explanation": (ex.get("explanation") or "").strip() or None,
            # Which numbered context section the model says it used. Not persisted
            # (finalize_exercise_set only reads known keys), it exists so the caller
            # can check that every section was actually served.
            "_section": ex.get("section"),
        })
        # The solved sentence carries the source content, so it is what gets attributed.
        claims.append(correct)
    return items, claims
