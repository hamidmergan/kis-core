"""A model verdict on finished grammar exercises, passed through when in doubt."""

import json

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json


# How the checker recognises a deliberately faulty statement.
_ON_PURPOSE = "wrong on purpose"

_SHAPE = (
    "Respond ONLY with a JSON object, one verdict per numbered sentence:\n"
    '{"verdicts": [{"i": 0, "ok": true}, '
    '{"i": 1, "ok": false, "why": "short reason"}]}\n'
)


def _prompt(target_form: str, rule: str) -> str:
    return (
        "You check finished grammar exercises before a learner sees them. Each numbered "
        "line is the sentence the learner ENDS UP WITH after solving the exercise, with "
        "the intended solution already put in.\n\n"
        f"Target form: {target_form}\n"
        f"Transformation rule: {rule}\n\n"
        "Mark an item ok=false ONLY when one of these three is true:\n"
        "1. With the solution in it, the sentence is not correct in its language: a word "
        "is doubled, a verb is left over, a part is missing. Read it back before you "
        "judge.\n"
        "2. The sentence does not show the target form at all.\n"
        "3. The sentence only STATES a rule about grammar instead of using the form. "
        'For example "Das Verb steht im Relativsatz immer am Ende." is a claim about '
        "grammar, not a sentence anybody practises a form in. A learner needs sentences "
        "that USE the form.\n\n"
        "Everything else is ok=true. Do NOT judge style, difficulty, wording, subject "
        "matter or how interesting a sentence is. Only the three points above.\n"
        f'A line marked "{_ON_PURPOSE}" carries a mistake the learner is supposed to '
        "spot. For those, check point 3 only, never point 1.\n"
        "Judge every sentence in the language it is written in. Never translate.\n"
        "Give exactly one verdict per number and keep the numbers as they are.\n\n"
        + _SHAPE
    )


def solved_text(ex: dict) -> str:
    """The sentence the learner is left with, or empty when there is none."""
    # Fetched only here, an import at the module header would close a cycle.
    from src.features.ai_assistant.tasks.language_training._source_grammar import GAP

    kind = (ex.get("kind") or "").strip().lower()
    if kind == "cloze":
        sentence = (ex.get("sentence") or "").strip()
        answer = ex.get("answer")
        answer = answer.strip() if isinstance(answer, str) else ""
        answer = answer or _marked_option(ex)
        return sentence.replace(GAP, answer) if sentence and answer else ""
    if kind == "statement":
        return (ex.get("statement") or "").strip()
    if kind == "transform":
        return (ex.get("after") or "").strip()
    if kind == "choice":
        return _marked_option(ex)
    return ""


def _marked_option(ex: dict) -> str:
    """The option marked correct, or empty."""
    options = ex.get("options") or []
    idx = ex.get("correct_idx")
    if not isinstance(idx, int) or isinstance(idx, bool):
        return ""
    if not 0 <= idx < len(options):
        return ""
    return str(options[idx]).strip()


def _wrong_on_purpose(ex: dict) -> bool:
    """Whether the exercise deliberately shows an error."""
    return (ex.get("kind") or "").strip().lower() == "statement" and \
        ex.get("answer") is False


def verdicts(client, model, exercises: list[dict], target_form: str,
             rule: str) -> list[bool]:
    """Per exercise, whether it is usable, True when in doubt."""
    if not exercises:
        return []
    urteile = [True] * len(exercises)

    lines = []
    for i, ex in enumerate(exercises):
        text = solved_text(ex)
        if not text:
            continue
        mark = f" ({_ON_PURPOSE})" if _wrong_on_purpose(ex) else ""
        lines.append(f"{i}.{mark} {text}")
    if not lines:
        return urteile

    messages = [{"role": "system", "content": _prompt(target_form, rule)},
                {"role": "user", "content": "\n".join(lines)}]
    try:
        # Low temperature: variety is not wanted here, a verdict is.
        response = client.chat.completions.create(
            model=model, messages=messages, temperature=0.2)
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
    except Exception as e:
        logger.warning("KI Tutor: Grammatik-Prüfung ausgefallen, Aufgaben ungeprüft: {}", e)
        return urteile

    gemeldet = (data.get("verdicts") or []) if isinstance(data, dict) else []
    for entry in gemeldet:
        if not isinstance(entry, dict):
            continue
        i = entry.get("i")
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(exercises):
            continue
        if not _is_rejected(entry.get("ok")):
            continue
        urteile[i] = False
        logger.info("KI Tutor: Grammatik-Aufgabe verworfen ({}): {}",
                    entry.get("why") or "kein Grund genannt", solved_text(exercises[i]))
    return urteile


def _is_rejected(value) -> bool:
    """Whether ok is a message, anything unknown counts as passed."""
    if value is False:
        return True
    return isinstance(value, str) and value.strip().casefold() in ("false", "no")
