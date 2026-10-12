"""Vocabulary cloze from source text, one text is exactly one exercise."""

import json
import re

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.services.aia_grammar_check import normalize

from src.features.ai_assistant.tasks.language_training._attribution import (
    PAGE_RULE,
    attach_chips_cited,
)
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.services.llm_call import create_logged


_PLACEHOLDER_RE = re.compile(r"\{\{(\d+)\}\}")

# Below this share of usable gaps the run counts as failed.
_MIN_USABLE_RATIO = 0.5

_SHAPE = (
    'Respond ONLY with a JSON object:\n'
    '{"title": "Short topic title", '
    '"instruction": "What the learner has to do, one or two sentences", '
    '"text": "The COMPLETE passage, fully written out with every target word in its correct '
    'form. No placeholders, no gaps, no brackets", '
    '"page": 12, '
    '"gaps": [{"base": "the dictionary form of the word", '
    '"solution": "the exact piece of the text that is the target word, copied letter for '
    'letter"}]}\n'
)

_RULES = (
    "RULES:\n"
    "- The passage is ONE coherent text about the source content, not a list of "
    "unrelated sentences. It must read as if it came from the material.\n"
    "- The code cuts the gaps out of your text afterwards: each 'solution' must appear in "
    "the text exactly once, spelled exactly as in the text, and the gaps array lists them "
    "in the order they appear.\n"
    "- Never put a base form, hint, bracket or translation next to a target word.\n"
    "- Never use the same base word twice.\n"
    "- A solution is used only at its own spot, never a second time in the passage.\n"
    "- 'base' is always the plain dictionary form, that is what the learner sees.\n"
    "- The instruction must say that some words keep their form and others do not.\n"
    "- Write a complete, natural, grammatically correct passage. Choose short, simple "
    "sentences with a clear structure, a sentence you are unsure about is replaced by a "
    "simpler one.\n"
    "- A solution is ONE unbroken piece of text that sits in its gap exactly as written. "
    "A word or phrase whose parts must stand in different places of the sentence "
    "(separable verbs, verb brackets, reflexive verbs split by the subject, verb-final "
    "word order after a subordinating conjunction) may only be a gap if the sentence "
    "keeps all of its parts together, such as the verb at the end of a subordinate "
    "clause or the participle/infinitive in its final position. Otherwise choose another "
    "sentence. Never put a multi-word solution in a gap when other words of the sentence "
    "belong between its parts.\n"
    "- Before you answer, reread the whole "
    "passage for grammar, word order, verb forms, punctuation and meaning. Pay special "
    "attention to word order after connectors (because, although, that, when) and to "
    "separable verbs. If anything is wrong, rewrite the sentence and the gap first.\n"
    "- A solution to AVOID (German): 'machte Fortschritte' in 'Obwohl sie Angst hatte, "
    "machte sie schnell Fortschritte.', because 'sie schnell' sits between the parts. "
    "Contiguous alternative: 'Obwohl sie Angst hatte, wollte sie schnell Fortschritte "
    "machen.' with the solution 'Fortschritte machen'.\n"
    "- A reflexive pronoun stands either inside the solution or in the text next to the "
    "gap, never in both. A solution to AVOID (German): 'sich lohnen' in 'Die Zeit wird "
    "sich sich lohnen.' Correct: 'Die Zeit wird sich lohnen.' with the solution 'sich "
    "lohnen'.\n"
)


def _min_inflected(count: int) -> int:
    """How many gaps must need a changed form at minimum."""
    bestellt = max(1, count)
    if bestellt == 1:
        return 1
    ziel = max(1, round(bestellt / 3))
    return min(ziel, bestellt - 1)  # nie alle, sonst bleibt keine unveraenderte Luecke


def _mix_rule(count: int) -> str:
    """Prompt lines for the form mix, a number plus a position that forces it."""
    bestellt = max(1, count)
    n = _min_inflected(bestellt)
    zeile = (
        f"- At least {n} of the {bestellt} gaps must need a form DIFFERENT from the "
        "dictionary form (a different ending, tense, case, or number) to be correct. "
        "A gap whose dictionary form already fits the sentence unchanged does NOT "
        "count towards this number, whichever word it is. Build the SENTENCE around a "
        "slot that FORCES the change, never pick a term first and hope the sentence "
        "happens to need a different form.\n"
        "- Slots that force a change: a verb the sentence needs to agree with its "
        "subject (never right after a modal verb, never a bare infinitive); an "
        "adjective placed directly in front of the noun it describes (it takes an "
        "ending there); a noun the sentence needs in the plural while its dictionary "
        "form is singular; a noun in a grammatical case that visibly changes its "
        "written form.\n"
    )
    # With exactly one gap there is no mix, the requirement is dropped.
    if bestellt > 1:
        zeile += (
            "- The gaps must not all be the same part of speech. Mix nouns, verbs, and "
            "adjectives across the gaps.\n"
            "- At least one gap must keep the dictionary form completely unchanged. "
            "Copying the same word into every gap fails this exercise just as much as "
            "changing it in every gap.\n"
        )
    return zeile


def placeholders(text: str) -> list[int]:
    """The placeholder numbers in the order they appear in the text."""
    return [int(m.group(1)) for m in _PLACEHOLDER_RE.finditer(text or "")]


# A short bracket directly after a placeholder.
_GAP_HINT_RE = re.compile(r"(\{\{(\d+)\}\})[ \t]*\(([^)]{1,80})\)")


def _strip_answer_hints(text: str, gaps: list) -> str:
    """Removes a bracket after a placeholder when it gives the solution away."""
    if not text or not gaps:
        return text

    def ersetze(m: re.Match) -> str:
        platzhalter, nummer_text, inhalt = m.group(1), m.group(2), m.group(3)
        nummer = int(nummer_text)
        if not (1 <= nummer <= len(gaps)):
            return m.group(0)
        gap = gaps[nummer - 1]
        if not isinstance(gap, dict):
            return m.group(0)
        verraten = {normalize(gap.get("base") or ""), normalize(gap.get("solution") or "")}
        verraten.discard("")
        if verraten and normalize(inhalt) in verraten:
            return platzhalter
        return m.group(0)

    return _GAP_HINT_RE.sub(ersetze, text)


def _is_usable(gap, words: list[str] | None, gesehen: set[str]) -> bool:
    """Whether this gap may stay."""
    if not isinstance(gap, dict):
        return False
    base = (gap.get("base") or "").strip()
    solution = (gap.get("solution") or "").strip()
    if not base or not solution:
        return False
    schluessel = normalize(base)
    if not schluessel or schluessel in gesehen:
        return False
    if words is not None and schluessel not in {normalize(w) for w in words}:
        return False
    return True


def clean_gaps(text: str, gaps: list[dict], words: list[str] | None):
    """Fills unusable gaps and renumbers the usable ones."""
    text = text or ""
    im_text = set(placeholders(text))
    gesehen: set[str] = set()
    behalten: list[dict] = []
    ersatz: dict[int, str] = {}
    for i, gap in enumerate(gaps or [], start=1):
        if i not in im_text:
            # No spot in the text with this number, there is nothing to do.
            continue
        if _is_usable(gap, words, gesehen):
            gesehen.add(normalize(gap["base"]))
            behalten.append({"base": gap["base"].strip(),
                             "solution": gap["solution"].strip()})
            ersatz[i] = "{{%d}}" % len(behalten)
        else:
            loesung = gap.get("solution") if isinstance(gap, dict) else None
            ersatz[i] = (loesung or "").strip()
    neu = _PLACEHOLDER_RE.sub(lambda m: ersatz.get(int(m.group(1)), ""), text)
    return neu, behalten


def _solved(text: str, gaps: list[dict]) -> str:
    """The model solution: the same text with the answers filled in."""
    return _PLACEHOLDER_RE.sub(
        lambda m: gaps[int(m.group(1)) - 1]["solution"] if 0 < int(m.group(1)) <= len(gaps) else "",
        text,
    )


def _build_prompt(count: int, language: str, words: list[str] | None) -> str:
    kopf = (
        f"You write a vocabulary gap-fill exercise from the given source text. "
        f"Write the passage and the instruction in {language}, "
        f"regardless of the source-text language.\n\n"
    )
    auftrag = f"Create a passage with exactly {count} gaps.\n\n"
    if words:
        liste = ", ".join(words)
        auftrag += (
            "Use ONLY these words as the gaps, nothing else. Every gap's 'base' must "
            f"be one of them, spelled exactly as given:\n{liste}\n\n"
        )
    else:
        auftrag += (
            "Pick the words yourself: the technical terms of the source material, the "
            "ones a learner of the subject has to know.\n\n"
        )
    return kopf + auftrag + _SHAPE + _RULES + _mix_rule(count) + PAGE_RULE


def _cut_gaps(text: str, gaps: list) -> tuple[str, list]:
    """Cuts each solution out of the finished passage and numbers the gaps by position."""
    if not text or not isinstance(gaps, list):
        return text, gaps
    treffer: list[tuple[int, int, dict]] = []
    for gap in gaps:
        loesung = (gap.get("solution") or "").strip() if isinstance(gap, dict) else ""
        if not loesung:
            continue
        muster = re.compile(r"(?<!\w)" + re.escape(loesung) + r"(?!\w)", re.IGNORECASE)
        funde = list(muster.finditer(text))
        # Missing or ambiguous: the spot is unclear, so the gap is dropped.
        if len(funde) != 1:
            continue
        m = funde[0]
        # Keep the spelling the text really has.
        treffer.append((m.start(), m.end(), {**gap, "solution": m.group(0)}))
    treffer.sort(key=lambda t: t[0])
    teile, geordnet, pos = [], [], 0
    for start, ende, gap in treffer:
        if start < pos:
            continue
        geordnet.append(gap)
        teile.append(text[pos:start])
        teile.append("{{%d}}" % len(geordnet))
        pos = ende
    teile.append(text[pos:])
    return "".join(teile), geordnet


def _generate_once(
    client, model,
    ctx: QuelleContext,
    count: int,
    words: list[str] | None = None,
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
):
    """One call, one text, one exercise, or None when nothing usable came back."""
    prompt = _build_prompt(count, language, words) + adaptive_suffix + title_avoidance
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Write the output in {language}.\n\n"
                                    f"Sources:\n\n{ctx.context}"},
    ]
    try:
        response = create_logged(client, endpoint="wortschatz", model=model, messages=messages,
                                      temperature=0.3)
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
    except Exception as e:  # noqa: BLE001
        logger.warning("KI Tutor: Lückentext nicht lesbar: {}", e)
        return None
    if not isinstance(data, dict):
        return None
    # A wrong shape is a failed run and not a crash.
    if not isinstance(data.get("text"), str) or not isinstance(data.get("gaps"), list):
        logger.warning("KI Tutor: Lückentext-Antwort hatte die falsche Form")
        return None

    # A finished passage without placeholders gets its gaps cut out here.
    if not placeholders(data["text"]):
        data["text"], data["gaps"] = _cut_gaps(data["text"], data["gaps"])
    # Remove the revealing brackets first, then count the placeholders.
    roh_text = _strip_answer_hints(data.get("text"), data.get("gaps"))
    text, gaps = clean_gaps(roh_text, data.get("gaps"), words)
    bestellt = max(1, count)
    if not gaps or len(gaps) < bestellt * _MIN_USABLE_RATIO:
        logger.warning("KI Tutor: Lückentext hatte nur {} von {} brauchbaren Lücken",
                       len(gaps), bestellt)
        return None

    # The title is decided before the exercise because it travels into extras.
    title = (data.get("title") or "").strip() or ctx.multi_label

    item = {
        "front": text,
        "back": _solved(text, gaps),
        # Instruction and title live in extras, the pool carries no set columns. No example
        # any more, the view dropped it on 31.08.2026 and writing it cost every run.
        "extras": {
            "gaps": gaps,
            "instruction": (data.get("instruction") or "").strip(),
            "title": title,
        },
        # With an underscore, because _attribution.py reads exactly this field.
        "_page": data.get("page"),
        # _kind carries the gap count into the pool so a request can filter on it.
        "_kind": str(len(gaps)),
    }
    # Layered attribution, because the cloze is written from scratch.
    attach_chips_cited([item], [item["back"]], ctx)

    return [item], title


_PROOF_PROMPT = (
    "You are a strict proofreader of {language}. Below is a finished passage. Check every "
    "sentence for grammar, word order (verb position in main and subordinate clauses, "
    "separable verbs, verb brackets), verb forms, case, reflexive pronouns (each used once, "
    "not twice), punctuation and meaning. Be strict: a sentence that a native speaker "
    "would not write is an error. Answer with JSON only: {{\"errors\": [\"<the faulty "
    "sentence> - <what is wrong>\"]}}. An empty list means the passage is flawless."
)


def _proofread(client, model, passage: str, language: str) -> list[str]:
    """Faulty sentences of the solved passage; empty when flawless or the check fails."""
    try:
        response = create_logged(
            client, endpoint="wortschatz", model=model, temperature=0,
            messages=[
                {"role": "system", "content": _PROOF_PROMPT.format(language=language)},
                {"role": "user", "content": passage},
            ],
        )
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
        errors = data.get("errors") if isinstance(data, dict) else None
    except Exception as e:  # noqa: BLE001
        logger.warning("KI Tutor: Lückentext-Prüfung nicht lesbar: {}", e)
        return []
    return [str(x) for x in errors if x] if isinstance(errors, list) else []


_MAX_ATTEMPTS = 5


def generate_cloze_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    words: list[str] | None = None,
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
):
    """Write the cloze, let a second call proofread the solved text, retry on errors."""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        result = _generate_once(client, model, ctx, count, words, language,
                                adaptive_suffix, title_avoidance)
        if result is None:
            continue
        errors = _proofread(client, model, result[0][0]["back"], language)
        if not errors:
            return result
        logger.warning("KI Tutor: Lückentext Versuch {} verworfen: {}", attempt, errors[:3])
    return None


def usable_flashcard_set(ex_set: dict | None, workspace_id: int, user_id: int) -> bool:
    """Whether this flashcard set may supply the words for a cloze."""
    return bool(
        ex_set
        and ex_set.get("workspace_id") == workspace_id
        and ex_set.get("user_id") == user_id
        and ex_set.get("tool") == "flashcards"
        and ex_set.get("status") == "ready"
    )


def run_cloze_set(set_id, ex_set, user_id, count, client, model,
                  language, adaptive_suffix, uuids) -> None:
    """Completes a cloze set: pool, otherwise generate, then save."""
    from src import database as db
    from src.features.ai_assistant.tasks.language_training._context import build_source_context
    from src.features.ai_assistant.tasks.language_training._pool import (
        pool_level, store as store_in_pool, take as take_from_pool, uses_pool,
    )
    from src.features.ai_assistant.tasks.language_training._variation import (
        build_title_avoidance_block,
    )

    mode = ex_set.get("mode") or "source"
    if not uuids:
        db.fail_exercise_set(set_id)
        return

    # From flashcards the fronts are the word list.
    words = None
    if mode == "cards":
        karten = db.get_exercise_set_with_items(ex_set.get("flashcard_set_id"))
        if not karten or not karten.get("items"):
            db.fail_exercise_set(set_id)
            return
        words = [i["front"] for i in karten["items"] if (i.get("front") or "").strip()]
        count = min(count, len(words))
        if not words:
            # A set with nothing but empty fronts is not really a set.
            db.fail_exercise_set(set_id)
            return

    level = pool_level(adaptive_suffix, user_id)
    # A pool row is a WHOLE text, hence exactly one and not `count`.
    if uses_pool(tool="wortschatz", mode=mode):
        # kinds filters the pool down to the ordered gap count.
        aus_vorrat = take_from_pool(uuids, "wortschatz", level, user_id, 1,
                                    kinds=[str(count)])
        if aus_vorrat:
            logger.info("KI Tutor: Satz {} nimmt seinen Text aus dem Vorrat", set_id)
            # The title lives in extras.title, the set row still carries the placeholder here.
            titel = (aus_vorrat[0].get("extras") or {}).get("title") or "Lückentext"
            db.finalize_exercise_set(set_id, titel, aus_vorrat, user_id=user_id)
            return

    # The gaps size the context, a section quota would break the continuous text apart.
    ctx = build_source_context(uuids, "wortschatz", count, with_quota=False)
    if ctx is None:
        db.fail_exercise_set(set_id)
        return
    # Without this a second set from the same document would get the same title.
    title_avoidance = build_title_avoidance_block(ex_set.get("workspace_id"), "wortschatz")
    result = generate_cloze_from_source(
        client, model, ctx, count, words=words, language=language,
        adaptive_suffix=adaptive_suffix, title_avoidance=title_avoidance,
    )
    if result is None:
        db.fail_exercise_set(set_id)
        return
    items, title = result
    if uses_pool(tool="wortschatz", mode=mode):
        store_in_pool(items, ctx, "wortschatz", level)
    # _kind has served its purpose and has no place in the saved set.
    for item in items:
        item.pop("_kind", None)
    # No header, the instruction hangs in extras on the exercise.
    db.finalize_exercise_set(set_id, title, items, user_id=user_id)


__all__ = ["clean_gaps", "generate_cloze_from_source", "placeholders",
           "run_cloze_set", "usable_flashcard_set"]
