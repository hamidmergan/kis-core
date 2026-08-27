"""Turns a typed topic name into a rule and a pattern example."""

import json

from loguru import logger

from src.features.ai_assistant.repository.grammar_topics import MAX_EXAMPLES
from src.services.aia_grammar_check import normalize


_PROMPT = (
    "A teacher wants their students to practise a grammar topic. You turn the topic "
    "name into a machine-readable description.\n\n"
    "Respond ONLY with a JSON object:\n"
    '{"is_grammar": true, '
    '"rule": "One paragraph in English naming the input form and the expected output '
    'form of the transformation", '
    '"label": "The exact name of the form you worked out, in {language}", '
    '"examples": [{"before": "A sentence in the original form", '
    '"after": "The same sentence transformed"}], '
    '"task_lines": {"transform": "...", "cloze": "...", "statement": "...", '
    '"choice": "..."}}\n\n'
    "Rules:\n"
    '- "is_grammar" asks ONE question: does the name say something about how a '
    "sentence is BUILT, rather than what it is about? Word order, case, tense, mood, "
    "voice, sentence type and style contrasts such as Nominalstil versus Verbalstil "
    "all qualify, and so does a teaching mnemonic for one of them, even an obscure "
    'one: German "tekamolo" is the order temporal, kausal, modal, lokal, so it is a '
    "grammar topic. A name you do not recognise is not automatically nonsense. It is "
    "false for subject matter (photosynthesis), for a person, and for a string that "
    "says nothing about sentence structure. Then return an empty rule and an empty "
    "list.\n"
    '- "rule" is read by another model and never by a learner. Name the input form '
    "and the output form precisely, the way a grammar reference would.\n"
    '- "label" names the ONE form that the rule and the example actually describe, '
    "not the broader area the teacher typed. Resolve an ambiguous name: German "
    '"Passiv" covers nine different forms, so write "Passiv Präsens" when your example '
    "is in the present tense. At most five words, the way a course topic is titled. "
    "No quotes and no sentence.\n"
    "- Give exactly ONE example. 'before' and 'after' are each ONE sentence and must "
    "differ from each other, otherwise there is nothing to practise.\n"
    "- Write the example in {language}, whatever language the topic name is written in.\n"
    "- Use no personal names. Write 'die Dozentin', 'das Team' or 'the lecturer' "
    "instead, matching the output language.\n"
    '- "task_lines" are the four instructions a learner reads above an exercise, one per '
    "exercise kind, in {language}. They MUST name this topic in a grammatically correct "
    "sentence. Inflect it, do not paste the topic name into a fixed frame: for a plural "
    "or feminine topic a frame like \"Setze den Satz ins ...\" produces nonsense.\n"
    "  transform: the learner rewrites the sentence into this form. A worked example "
    "sits above that exercise, so point at it where it reads naturally, INSIDE the "
    "sentence and never as a comma-separated tail. Leave it out rather than force it.\n"
    "  cloze: the learner fills one missing word in this form.\n"
    "  statement: the learner judges whether the sentence is correct in this form.\n"
    "  choice: the learner picks which of several sentences is correct in this form.\n"
    "  Each is ONE short sentence, addressed to the learner, ending in a full stop or a "
    "question mark. No quotes around the topic name.\n"
    "  Write the sentence a teacher would write. Rephrase whatever the teacher typed "
    "until it fits: a topic name may be plural, may be an area rather than a form, may "
    "name a word-order rule, or may bundle several topics at once. Copy these shapes:\n"
    '    "Relativsatz" -> transform: "Forme den Satz nach dem Beispiel in einen '
    'Relativsatz um."   NOT "Setze den Satz ins Relativsatz, nach dem Beispiel."\n'
    '    "Adjektivdeklination ohne Artikel" -> transform: "Forme den Satz in einen Satz '
    'mit Adjektivdeklination ohne Artikel um."\n'
    '    "tekamolo" -> transform: "Bilde den Satz nach der tekamolo-Regel."\n'
    '    "Finalsätze Nominalstil Verbalstil" -> transform: "Forme den Satz nach dem '
    'Beispiel vom Nominalstil in den Verbalstil um."\n'
)


def derive_topic(client, model, name: str, language: str) -> dict | None:
    """Rule and pattern example for a topic name, or None."""
    # Fetched only here, an import at the module header would close a cycle.
    from src.features.ai_assistant.tasks._helpers import _clean_llm_json

    # language may be a name or a code, a code would otherwise end up verbatim in the prompt.
    from src.i18n import TRANSCRIPT_LANGUAGES
    eintrag = TRANSCRIPT_LANGUAGES.get((language or "").lower())
    # Not 'label', that is the field name of the suggested name.
    sprach_label = eintrag["name"] if eintrag else (language or "German")
    messages = [
        {"role": "system", "content": _PROMPT.replace("{language}", sprach_label)},
        {"role": "user",
         "content": f"Topic: {name}\n\nWrite the example in {sprach_label}."},
    ]
    # Low temperature, what is wanted is the safest reading of the topic name.
    response = client.chat.completions.create(
        model=model, messages=messages, temperature=0.2)
    try:
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
    except Exception as e:
        # An unusable answer is a refusal, not a disruption.
        logger.warning("Grammatik-Thema {!r} nicht lesbar beantwortet: {}", name, e)
        return None

    if not isinstance(data, dict) or not data.get("is_grammar"):
        logger.info("Grammatik-Thema {!r} abgelehnt, kein Grammatikthema", name)
        return None

    rule = (data.get("rule") or "").strip()
    examples = [pair for pair in (data.get("examples") or []) if is_usable_pair(pair)]
    if not rule or not examples:
        logger.info("Grammatik-Thema {!r} abgelehnt, Regel oder Beispiel fehlt", name)
        return None
    return {"rule": rule, "examples": examples[:MAX_EXAMPLES],
            "task_lines": usable_task_lines(data.get("task_lines")),
            # Which form the model made out of the typed name.
            "label": usable_label(data.get("label"))}


def derive_task_lines(client, model, name: str, language: str) -> dict:
    """Backfills only the instruction lines, rule and pattern pair stay untouched."""
    try:
        derived = derive_topic(client, model, name, language)
    except Exception as e:
        logger.warning("Anweisungszeilen fuer {!r} nicht nachgereicht: {}", name, e)
        return {}
    return (derived or {}).get("task_lines") or {}


# The four exercise formats, each needing one instruction.
TASK_KINDS = ("transform", "cloze", "statement", "choice")


def usable_task_lines(lines) -> dict:
    """The instruction lines, only when all four are usable, empty otherwise."""
    if not isinstance(lines, dict):
        return {}
    fertig = {}
    for kind in TASK_KINDS:
        text = (lines.get(kind) or "").strip()
        # An empty or one-word instruction is none.
        if not text or len(text.split()) < 3:
            return {}
        fertig[kind] = text
    return fertig


# A topic name and not a sentence, longer means misunderstood.
MAX_LABEL_CHARS = 60


def usable_label(value) -> str:
    """The suggested name, empty is not an error."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or len(text) > MAX_LABEL_CHARS or len(text.splitlines()) > 1:
        return ""
    return text


def is_usable_pair(pair) -> bool:
    """Whether anything really changes between before and after."""
    if not isinstance(pair, dict):
        return False
    before = (pair.get("before") or "").strip()
    after = (pair.get("after") or "").strip()
    if not before or not after:
        return False
    return normalize(before) != normalize(after)
