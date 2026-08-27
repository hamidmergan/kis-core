"""Grammar exercise from source text, the sentences are rebuilt instead of copied."""

import json
import re

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json

from src.features.ai_assistant.tasks.language_training._attribution import (
    PAGE_RULE,
    attach_chips_cited,
)
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._plan import (
    plan_sentence,
    room_left,
    still_missing,
)
from src.services.aia_grammar_check import normalize, overlap_ratio
from src.services.aia_grammar_formats import KINDS
from src.services.llm_context_healing import create_with_shrink


_SHAPE = (
    'Respond ONLY with a JSON object. Every exercise carries its "kind", its "page" '
    'and a short "explanation" naming the form that decides it:\n'
    '{"title": "Short topic title", "exercises": [\n'
    '  {"kind": "transform", "before": "Sentence in the original form", '
    '"after": "The same sentence transformed", "also_ok": ["Another wording that is '
    'just as correct"], "explanation": "...", "page": 12},\n'
    '  {"kind": "cloze", "sentence": "A complete, correct sentence showing the target '
    'form, with NO gap in it", "form_span": "The part of that sentence which carries '
    'the form, copied out of it character for character", '
    '"options": ["...", "...", "...", "..."], '
    '"correct_idx": 0, "explanation": "...", "page": 12},\n'
    '  {"kind": "statement", "statement": "A sentence that either shows the target '
    'form correctly or gets it wrong", "answer": true, "explanation": "...", '
    '"page": 12},\n'
    '  {"kind": "choice", "task": "The form the learner has to produce", '
    '"sentence": "The statement to transform", '
    '"options": ["...", "...", "...", "..."], "correct_idx": 0, '
    '"explanation": "...", "page": 12}\n'
    ']}\n'
)

# Fixed labels for true/false instead of ones invented by the model.
_VERDICT_LABELS = {"de": ("Richtig", "Falsch"), "en": ("True", "False")}

# Question marks across writing systems, a question cannot be reshaped.
_QUESTION_MARKS = "?？؟;՞।"

# The instruction to the learner, one per format, with the topic name after a colon.
_TASK_LINES = {
    "de": {
        "transform": "Forme den Satz nach dem Beispiel um. Zielform: {form}.",
        "cloze": "Ergänze das fehlende Wort. Zielform: {form}.",
        "statement": "Ist der Satz korrekt? Zielform: {form}.",
        "choice": "Welcher Satz ist korrekt? Zielform: {form}.",
    },
    "en": {
        "transform": "Rewrite the sentence following the example. Target form: {form}.",
        "cloze": "Fill in the missing word. Target form: {form}.",
        "statement": "Is the sentence correct? Target form: {form}.",
        "choice": "Which sentence is correct? Target form: {form}.",
    },
}


def task_line(kind: str, locale: str, target_form: str, eigene: dict | None = None) -> str:
    """The instruction for a format, in the language of the set."""
    fertig = (eigene or {}).get(kind)
    if fertig and fertig.strip():
        return fertig.strip()
    lines = _TASK_LINES.get(locale, _TASK_LINES["en"])
    return lines.get(kind, lines["transform"]).replace("{form}", target_form)


# Below this rate a run counts as failed.
_MIN_USABLE_RATIO = 0.5

# Up to three attempts so the ordered number comes together.
_MAX_ATTEMPTS = 3

# Four options in multiple choice, fewer looks wrong and more does not fit.
_OPTION_COUNT = 4

# From this word overlap on a wrong option counts as a form variant.
_MIN_OPTION_OVERLAP = 0.5

# This is how a gap is written, three underscores are recognisable in the text.
GAP = "___"

# Outer word boundary for the form carrier, the real rule is in is_usable_cloze.
_MAX_SPAN_WORDS = 4

# From this length on a word of the topic name counts as a technical term.
_MIN_TERM_CHARS = 6


def item_plan(count: int, kinds=None) -> list[str]:
    """Which exercise gets which format, round robin and as a number in the prompt."""
    verfuegbar = list(kinds) if kinds else list(KINDS)
    return [verfuegbar[i % len(verfuegbar)] for i in range(max(0, count))]


def generate_grammar_from_source(
    client, model,
    ctx: QuelleContext,
    grammar_type: dict,
    count: int,
    locale: str = "de",
    # The exercise sentences follow the source language, only the frame the teaching language.
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
    # The chosen formats steer the distribution and filter at the same time.
    kinds: list[str] | None = None,
) -> tuple[list[dict], str, dict]:
    """Returns exercises, title and header, empty means the run is unusable."""
    target_form = grammar_type["label"]
    shipped_example = grammar_type["example"]
    plan = item_plan(count, kinds)
    # No target language, the exercise sentences stay in the source language.
    user_msg = f"Sources:\n\n{ctx.context}"

    def messages_for(wanted: list[str]) -> list[dict]:
        prompt = (
            _build_prompt(grammar_type, target_form, shipped_example, wanted)
            + adaptive_suffix + title_avoidance + coverage
        )
        return [{"role": "system", "content": prompt},
                {"role": "user", "content": user_msg}]
    # A second attempt when the first delivers too little that is usable.
    items: list[dict] = []
    claims: list[str] = []
    seen: set = set()
    seen_exercises = 0
    data: dict = {}
    for attempt in range(_MAX_ATTEMPTS):
        # The top-up asks only for what is missing, otherwise the mix tips over.
        wanted = still_missing(plan, items)
        if not wanted:
            break
        last_try = attempt == _MAX_ATTEMPTS - 1
        if last_try:
            # In the last attempt the count matters more than the mix, but only within the selection.
            wanted = _fallback_kinds(items, wanted, kinds)
        # The same temperature as the other tools, still JSON safe.
        response = create_with_shrink(client, endpoint="grammatik", model=model, messages=messages_for(wanted), temperature=0.6)
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
        exercises = list(data.get("exercises") or [])[:count]
        seen_exercises += len(exercises)
        fresh, fresh_claims = _build_items(exercises, locale, shipped_example, target_form,
                                           grammar_type.get("task_lines"))
        # Until the last attempt the per-format cap applies, after that the count counts.
        room = {} if last_try else room_left(plan, items)
        for item, claim in zip(fresh, fresh_claims):
            # Key from exercise text and solution, otherwise two exercises look the same up front.
            key = (normalize(item["front"]), normalize(item["back"]))
            if key in seen:
                continue
            kind = item.get("_kind")
            # A deselected kind is always discarded, in the last attempt too.
            if kinds and kind not in kinds:
                continue
            if not last_try:
                if room.get(kind, 0) <= 0:
                    continue
                room[kind] -= 1
            seen.add(key)
            items.append(item)
            claims.append(claim)
        if len(items) >= count:
            break
        logger.info("KI Tutor: Grammatik-Wurf {} ergab {}/{} Aufgaben",
                    attempt + 1, len(items), count)
    items, claims = items[:count], claims[:count]

    # Too many comprehension questions and the whole run is thrown away.
    wanted = min(count, seen_exercises) or count
    if len(items) < max(1, int(wanted * _MIN_USABLE_RATIO)):
        logger.warning(
            "KI Tutor: grammar run discarded, only {}/{} sentences were usable",
            len(items), wanted,
        )
        return [], "", {}

    # Layered attribution, because the sentences are invented and then reshaped.
    attach_chips_cited(items, claims, ctx)

    # _kind stays on the exercise, it carries the form into the pool.

    title = (data.get("title") or "").strip() or grammar_type["label"]
    # No set header any more, the pattern hangs on the exercise that needs one.
    return items, title, {}


def _fallback_kinds(have: list[dict], missing: list[str], kinds=None) -> list[str]:
    """Which kinds the last attempt orders: the ones that already delivered."""
    erlaubt = [k for k in KINDS if not kinds or k in kinds]
    geklappt = [kind for kind in erlaubt if any(i.get("_kind") == kind for i in have)]
    if not geklappt:
        return missing
    return [geklappt[i % len(geklappt)] for i in range(len(missing))]


def _build_prompt(grammar_type: dict, target_form: str, example: dict,
                  plan: list) -> str:
    # The pattern pair goes along as a form to imitate, a bare rule has no effect.
    shape = (
        "SHAPE TO COPY. Every exercise looks exactly like this pair:\n"
        f'  before: "{example["before"]}"\n'
        f'  after:  "{example["after"]}"\n\n'
        "NOT like these, they are all wrong here:\n"
        '  "Was bedeutet wissenschaftliches Arbeiten?"  (a question, cannot be transformed)\n'
        '  "Nennen Sie drei Beispiele."                 (an instruction, not a statement)\n'
        '  "Wissenschaftliches Arbeiten"                (not a sentence)\n\n'
        # A separate example for multiple choice, the rule alone has no effect.
        "OPTIONS TO COPY, for kind \"choice\". Note how all four say the SAME thing "
        "about the SAME people and differ only in the verb form:\n"
        '  "Der Bericht wird vom Team geschrieben."      <- the correct one\n'
        '  "Der Bericht ist vom Team geschrieben."\n'
        '  "Der Bericht wird vom Team schreiben."\n'
        '  "Der Bericht wurde vom Team geschrieben."\n\n'
        "NOT like this, it changes who does what instead of the form:\n"
        '  "Das Team wird geschrieben."\n\n'
    )
    return (
        "You build a grammar drill from the given source text. "
        "Write ALL exercise sentences in the SAME language as the source text. "
        "Do NOT translate them into any other language.\n\n"
        # The instruction to the learner deliberately stays out, it names no form.
        f"Target form: {target_form}\n"
        f"Transformation rule: {grammar_type['rule']}\n\n"
        + shape +
        f"Write exactly {len(plan)} exercises: {plan_sentence(plan)}. The SAME target "
        "form throughout, only the way the learner answers changes.\n\n"
        "What each kind is:\n"
        "- transform: the learner rewrites 'before' into 'after' themselves.\n"
        # The code cuts the gap, the model delivers sentence plus excerpt.
        "- cloze: write a COMPLETE, correct sentence that shows the target form, with "
        "NO gap in it. 'form_span' is the part of that sentence which carries the form, "
        "copied out of it character for character, at most three words. The software "
        "cuts the gap, not you. Whatever stands in 'form_span' is what the learner "
        "fills in, so the sentence has to read correctly with it:\n"
        '    sentence "Die Messwerte werden vom Server gespeichert.", '
        'form_span "werden"\n'
        "  Give four short options, all different, one of them exactly 'form_span', the "
        "other three forms a learner actually confuses. 'correct_idx' points at "
        "'form_span' and counts from 0.\n"
        "- statement: a sentence that either shows the target form correctly or gets it "
        "wrong. 'answer' is true when it is correct. About half of them are false, and a "
        "false one is wrong in exactly ONE detail of the form. It is a sentence that "
        "USES the form, never a claim ABOUT grammar. Wrong here, it states a rule "
        'instead of practising it: "Das Verb steht im Relativsatz immer am Ende."\n'
        "- choice: four options that differ ONLY in form, same words, same content. "
        "Every option is a COMPLETE SENTENCE, never a single word and never a bare "
        "verb form, because the learner picks a finished sentence. Exactly one is "
        "correct, the other three are mistakes a learner actually makes. "
        "'correct_idx' counts from 0.\n\n"
        "How to build the sentences:\n"
        "- Take the FACTS, terms and topics from the source text and write NEW, simple "
        "sentences about them. Never copy a sentence from the source verbatim.\n"
        "- Never copy exercises that may already be in the source text. The source supplies "
        "subject matter, not exercises.\n"
        # A sentence naming the target form is dropped in the code as well.
        "- Never NAME the target form inside a sentence. The exercises practise the "
        "form, they never talk about it. If the source text is itself about grammar, "
        "take the subject matter from its example sentences (fire safety, rescue "
        "systems, measurements) and never its rules.\n"
        "- Every sentence is a STATEMENT. Never a question, never an instruction to the "
        "learner, never a bare phrase.\n"
        "- Every 'before' MUST be a valid input for the transformation rule above. "
        "If the rule needs a modal verb, every sentence contains one.\n"
        "- 'after' is the expected solution, correct and complete, and it must "
        "differ from 'before'.\n"
        # Every valid version must be listed here, checking only compares.
        "- 'also_ok' lists OTHER wordings of the same transformation that are just as "
        "correct, up to two. Work them out for every sentence before you move on:\n"
        '    before "Ich habe keine Zeit.", after "Ich hätte Zeit.", '
        'also_ok ["Ich würde Zeit haben."]\n'
        '    before "Der Server speichert die Messwerte.", '
        'after "Die Messwerte werden vom Server gespeichert.", '
        'also_ok ["Die Messwerte werden gespeichert."]\n'
        "  Typical cases are a different word order, an equally correct alternative "
        "form, and an optional part left out. The learner's answer is marked by "
        "comparing it against 'after' and this list and nothing else, so a valid "
        "wording missing here is marked as a mistake. An empty list is the rare "
        "exception, only when no other correct wording exists at all.\n"
        # No length rule, the difficulty comes from the language level alone.
        "- Every sentence is exactly ONE sentence.\n"
        "- Do NOT use personal names. Write 'die Dozentin', 'das Team', 'according to the source' "
        "instead, matching the output language.\n"
        # The pattern sentence must not appear as an exercise itself.
        "- The worked pair above is a SHAPE, never an exercise. Never reuse its "
        "sentence, not as 'before', not in a gap sentence, not as an option.\n"
        + PAGE_RULE + "\n"
        + _SHAPE
    )


def is_usable_pair(before: str, after: str) -> bool:
    """Whether a generated sentence pair is solvable for a learner at all."""
    if not before or not after:
        return False
    if before[-1] in _QUESTION_MARKS or after[-1] in _QUESTION_MARKS:
        return False
    if normalize(before) == normalize(after):
        return False
    # A single word (or none) is a heading, not a sentence to transform.
    return len(before.split()) >= 3


def is_usable_statement(text: str, verdict) -> bool:
    """Whether a true/false statement can be judged."""
    text = (text or "").strip()
    if not text or not isinstance(verdict, bool):
        return False
    if text[-1] in _QUESTION_MARKS:
        return False
    # Two words are a heading, not a statement.
    return len(text.split()) >= 3


def cut_gap(sentence: str, form_span: str) -> str | None:
    """The sentence with the gap where the form carrier was, or None."""
    sentence = (sentence or "").strip()
    span = (form_span or "").strip()
    if not sentence or not span:
        return None
    # A gap takes a form, not half a sentence.
    if len(span.split()) > _MAX_SPAN_WORDS:
        return None
    # Appearing several times is not unambiguous, it would make two gaps.
    stelle = re.compile(rf"(?<!\w){re.escape(span)}(?!\w)")
    if len(stelle.findall(sentence)) != 1:
        return None
    gapped = stelle.sub(GAP, sentence, count=1)
    # Only a gap and nothing else is not a sentence but an empty field.
    if len(gapped.replace(GAP, " ").split()) < 3:
        return None
    return gapped


def names_the_form(text: str, target_form: str) -> bool:
    """Whether the sentence names the target form and is thus a rule instead of an exercise."""
    woerter = set(normalize(text).split())
    if not woerter:
        return False
    return any(begriff in woerter
               for begriff in normalize(target_form).split()
               if len(begriff) >= _MIN_TERM_CHARS)


def is_usable_cloze(sentence: str, form_span: str, options: list, correct_idx) -> bool:
    """Whether sentence and form carrier make a solvable gap."""
    if cut_gap(sentence, form_span) is None:
        return False

    if not options or len(options) != _OPTION_COUNT:
        return False
    if not isinstance(correct_idx, int) or isinstance(correct_idx, bool):
        return False
    if not 0 <= correct_idx < len(options):
        return False
    normalized = [normalize(opt) for opt in options]
    if not all(normalized):
        return False
    # The same answer twice: the learner can be right and wrong at once.
    if len(set(normalized)) != len(normalized):
        return False
    # No word may appear in all four options, that is the guard against oversized gaps.
    if set.intersection(*(set(n.split()) for n in normalized)):
        return False
    # The marked option must be the form carrier.
    return normalized[correct_idx] == normalize(form_span)


def is_usable_choice(task: str, sentence: str, options: list, correct_idx) -> bool:
    """Whether a multiple choice exercise really practises a form."""
    if not task or not sentence:
        return False
    # One or two words are a heading, not a sentence to reshape.
    if len(sentence.split()) < 3:
        return False
    if not options or len(options) != _OPTION_COUNT:
        return False
    # bool is an int in Python, and True would quietly mean position 1.
    if not isinstance(correct_idx, int) or isinstance(correct_idx, bool):
        return False
    if not 0 <= correct_idx < len(options):
        return False

    normalized = [normalize(opt) for opt in options]
    if not all(normalized):
        return False
    # Two options that differ only in spelling are the same answer.
    if len(set(normalized)) != len(normalized):
        return False
    # The sentence may be the right option, as a wrong one it stays forbidden.
    if normalize(sentence) in normalized and normalized[correct_idx] != normalize(sentence):
        return False

    correct = options[correct_idx]
    return all(
        overlap_ratio(opt, correct) >= _MIN_OPTION_OVERLAP
        for i, opt in enumerate(options) if i != correct_idx
    )


def _build_items(exercises: list[dict], locale: str, example: dict,
                 target_form: str,
                 eigene_zeilen: dict | None = None) -> tuple[list[dict], list[str]]:
    """The exercise rows plus the text the source is matched by."""
    yes, no = _VERDICT_LABELS.get(locale, _VERDICT_LABELS["en"])
    # Pattern sentence and pattern solution must not come back as an exercise.
    banned = {normalize(example.get("before") or ""), normalize(example.get("after") or "")}
    banned.discard("")
    items, claims = [], []
    for ex in exercises:
        kind = (ex.get("kind") or "transform").strip().lower()
        built = _build_one(ex, kind, yes, no, example)
        if built is None:
            logger.debug("KI Tutor: Grammatik-Aufgabe verworfen ({}): {!r}", kind, ex)
            continue
        item, claim = built
        if _repeats_example(item["front"], banned):
            logger.debug("KI Tutor: Grammatik-Aufgabe wiederholt das Muster: {!r}",
                         item["front"])
            continue
        # A sentence naming the target form is a statement about the grammar.
        if names_the_form(claim, target_form):
            logger.debug("KI Tutor: Grammatik-Aufgabe nennt die Zielform: {!r}", claim)
            continue
        # The instruction sits on every exercise, with a blank line before it.
        anweisung = task_line(kind, locale, target_form, eigene_zeilen)
        item["front"] = (f"**{anweisung}**\n\n{item['front']}" if item["front"]
                         else f"**{anweisung}**")
        item["explanation"] = (ex.get("explanation") or "").strip() or None
        # Which section the model claims to have used, only for the coverage check.
        item["_section"] = ex.get("section")
        # The page the model names is checked and then removed.
        item["_page"] = ex.get("page")
        # Which kind the exercise became, only for counting the top-up.
        item["_kind"] = kind
        items.append(item)
        claims.append(claim)
    return items, claims


def _repeats_example(front: str, banned: set) -> bool:
    """Whether the exercise text repeats the pattern sentence, gapped version included."""
    plain = normalize(front.replace(GAP, " "))
    for text in banned:
        if not text:
            continue
        if plain == text:
            return True
        # Gapped version: the pattern sentence minus exactly one word.
        words, ref = plain.split(), text.split()
        if len(words) == len(ref) - 1 and all(w in ref for w in words):
            return True
    return False


def _build_one(ex: dict, kind: str, yes: str, no: str, example: dict):
    """One row for one format, or None when it fails the filter."""
    if kind == "transform":
        before = (ex.get("before") or "").strip()
        after = (ex.get("after") or "").strip()
        if not is_usable_pair(before, after):
            return None
        # Only the reshaping needs a pattern, otherwise it would be ballast.
        extras = {"pattern_front": example["before"],
                  "pattern_back": example["after"]}
        # Further valid versions, they carry the check without a model.
        accepts, seen = [], {normalize(after)}
        for alt in (ex.get("also_ok") or [])[:3]:
            alt = str(alt).strip()
            if not is_usable_pair(before, alt) or normalize(alt) in seen:
                continue
            seen.add(normalize(alt))
            accepts.append(alt)
        if accepts:
            extras["accepts"] = accepts
        return {"front": before, "back": after, "extras": extras}, after

    if kind == "cloze":
        sentence = (ex.get("sentence") or "").strip()
        span = (ex.get("form_span") or "").strip()
        options = [str(o).strip() for o in (ex.get("options") or [])]
        idx = ex.get("correct_idx")
        if not is_usable_cloze(sentence, span, options, idx):
            return None
        # The source hangs off the complete original sentence, not the gapped one.
        return ({"front": cut_gap(sentence, span), "back": options[idx],
                 "options": options, "correct_idx": idx},
                sentence)

    if kind == "statement":
        text = (ex.get("statement") or "").strip()
        verdict = ex.get("answer")
        if not is_usable_statement(text, verdict):
            return None
        return {"front": text, "back": yes if verdict else no,
                "options": [yes, no], "correct_idx": 0 if verdict else 1}, text

    if kind == "choice":
        task = (ex.get("task") or "").strip()
        sentence = (ex.get("sentence") or "").strip()
        options = [str(o).strip() for o in (ex.get("options") or [])]
        idx = ex.get("correct_idx")
        if not is_usable_choice(task, sentence, options, idx):
            return None
        # If the sentence is the right option it would otherwise appear twice.
        asks_which = normalize(sentence) == normalize(options[idx])
        return {"front": "" if asks_which else sentence, "back": options[idx],
                "options": options, "correct_idx": idx}, options[idx]

    # A kind that does not exist, guessing would be worse than leaving it out.
    return None
