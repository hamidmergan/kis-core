"""Turns a typed topic name into a rule and a pattern example."""

import json

from loguru import logger

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
    '"after": "The same sentence transformed"}]}\n\n'
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
    "and the output form precisely, the way a grammar reference would. When more than "
    "one standard construction correctly performs the same transformation, a "
    "different connector for the same relation say, name all of them here, even "
    "though the worked example below commits to only one.\n"
    '- "label" names the ONE form that the rule and the example actually describe, '
    "not the broader area the teacher typed. Resolve an ambiguous name: German "
    '"Passiv" covers nine different forms, so write "Passiv Präsens" when your example '
    "is in the present tense. At most five words, the way a course topic is titled. "
    "No quotes and no sentence.\n"
    "- Give exactly ONE example. 'before' and 'after' are each ONE sentence and must "
    "differ from each other, otherwise there is nothing to practise.\n"
    "- 'before' and 'after' must not say the same thing twice. If a word from "
    "'before' stays in 'after' unchanged, do not also insert a re-inflected copy of "
    "that same word elsewhere in 'after': \"Das Studienangebot ist groß.\" -> \"Das "
    "große Studienangebot ist groß.\" keeps \"ist groß\" and adds \"große\", so it "
    "says big twice. Rebuild the sentence so the predicate becomes the attribute "
    "instead of sitting there twice: \"Wir bewerben das große Studienangebot.\"\n"
    "- Write the example in {language}, whatever language the topic name is written in.\n"
    "- The person in the example is CONCRETE: a role ('die Professorin', 'der Student', "
    "'the lecturer') or an invented first name ('Jasmin', 'Max'), matching the output "
    "language. Never a vague subject such as 'das Team', 'die Person' or 'man'.\n"
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
    # The prompt asks for exactly one, further musterwege are the teacher's own
    # addition afterwards, never something the model hands over unprompted.
    return {"rule": rule, "examples": examples[:1],
            # Which form the model made out of the typed name.
            "label": usable_label(data.get("label"))}


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
    if normalize(before) == normalize(after):
        return False
    return not _repeats_a_word(before, after)


# Below this length a word (an article, a preposition) is too common to mean anything.
_MIN_STEM_CHARS = 3


def _repeats_a_word(before: str, after: str) -> bool:
    """Whether 'after' adds a re-inflected copy of a word 'before' already carries unchanged."""
    before_words = normalize(before).split()
    after_words = normalize(after).split()
    unchanged = [w for w in after_words if w in before_words]
    inserted = [w for w in after_words if w not in before_words]
    return any(
        len(old) >= _MIN_STEM_CHARS and new != old
        and (new.startswith(old) or old.startswith(new))
        for new in inserted for old in unchanged
    )
