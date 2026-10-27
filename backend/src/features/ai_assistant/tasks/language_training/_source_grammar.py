"""Grammar exercise from source text, the sentences are rebuilt instead of copied."""

import json
import random
import re

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json

from src.features.ai_assistant.tasks.language_training._attribution import (
    PAGE_RULE,
    attach_chips_cited,
)
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._grammar_verify import verdicts
from src.features.ai_assistant.tasks.language_training._plan import (
    plan_sentence,
    room_left,
    still_missing,
)
from src.services.aia_grammar_check import normalize
from src.services.aia_grammar_formats import KINDS
from src.features.ai_assistant.tasks._context_budget import exercise_max_tokens
from src.features.ai_assistant.prompts.language_training_prompts import COMPACT_JSON_RULE
from src.features.ai_assistant.tasks._json_commas import loads_entries
from src.services.llm_call import create_logged


_SHAPE = (
    'Respond ONLY with a JSON object. Every exercise carries its "kind", its "page" '
    'and a short "explanation" naming the form that decides it:\n'
    '{"title": "Short topic title", "exercises": [\n'
    '  {"kind": "transform", "before": "Sentence in the original form", '
    '"after": "The same sentence transformed", "also_ok": ["Another wording that is '
    'just as correct"], "explanation": "...", "page": 12},\n'
    '  {"kind": "cloze", "sentence": "A complete, correct sentence showing the target '
    'form, with NO gap in it", "form_span": "The part of that sentence which carries '
    'the form, copied out of it character for character", "base_form": "REQUIRED, '
    'never empty: the dictionary form of the word in form_span, never the finished '
    'answer", "also_ok": ["Another filling of the same gap that is just as correct"], '
    '"explanation": "...", "page": 12},\n'
    '  {"kind": "statement", "statement": "A sentence that either shows the target '
    'form correctly or gets it wrong", "answer": true, "explanation": "...", '
    '"page": 12},\n'
    '  {"kind": "choice", "before": "Sentence in the original form", "after": "The '
    'correct transformation of it", "wrong": ["An incorrect transformation of the SAME '
    '\'before\'", "A second, different incorrect transformation"], "explanation": "...", '
    '"page": 12}\n'
    ']}\n'
)

# Fixed labels for true/false instead of ones invented by the model.
_VERDICT_LABELS = {"de": ("Richtig", "Falsch"), "en": ("True", "False")}

# Question marks across writing systems, a question cannot be reshaped.
_QUESTION_MARKS = "?？؟;՞।"

# Several phrasings per format so a mixed set does not read identically. The
# topic name never appears in here, it only sits in the frame ahead of it,
# see task_line: never declined, never tied to a preposition or a verb.
_TASK_LINES = {
    "de": {
        "transform": [
            "Forme den Satz nach dem Beispiel um.",
            "Schreibe den Satz nach dem Beispiel um.",
            "Verändere den Satz entsprechend der Regel.",
        ],
        "cloze": [
            "Ergänze die Lücke.",
            "Setze die richtige Form ein.",
            "Vervollständige den Satz.",
            "Trage das passende Wort ein.",
        ],
        "statement": [
            "Ist folgender Satz richtig oder falsch?",
            "Stimmt dieser Satz?",
            "Prüfe den Satz: richtig oder falsch?",
        ],
        "choice": [
            "Welche Option ist korrekt?",
            "Kreuze die richtige Antwort an.",
            "Welche Antwort passt?",
            "Was ist richtig?",
        ],
    },
    "en": {
        "transform": [
            "Rewrite the sentence following the example.",
            "Transform the sentence following the example.",
            "Change the sentence according to the rule.",
        ],
        "cloze": [
            "Fill in the gap.",
            "Enter the correct form.",
            "Complete the sentence.",
            "Fill in the matching word.",
        ],
        "statement": [
            "Is the following sentence correct or wrong?",
            "Is this sentence correct?",
            "Check the sentence: correct or wrong?",
        ],
        "choice": [
            "Which option is correct?",
            "Tick the correct answer.",
            "Which answer fits?",
            "What is correct?",
        ],
    },
}

# The frame the topic name sits in, a label ahead of the instruction, never
# a sentence part: "Thema: „Präteritum". Ergänze die Lücke."
_TOPIC_LABEL = {"de": "Thema", "en": "Topic"}


def task_line(kind: str, locale: str, target_form: str) -> str:
    """The instruction for a format, the topic named only as a label ahead of it."""
    lines = _TASK_LINES.get(locale, _TASK_LINES["en"])
    variants = lines.get(kind) or lines["transform"]
    label = _TOPIC_LABEL.get(locale, _TOPIC_LABEL["en"])
    return f'{label}: „{target_form}". {random.choice(variants)}'


# Below this rate a run counts as failed.
_MIN_USABLE_RATIO = 0.5

# One generation call per set, the verdict call after it stays.
_MAX_ATTEMPTS = 1

# Share of extra exercises ordered on top, at least one.
_SPARE_SHARE = 0.2

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
    # Every stored musterweg, not only the one the learner sees.
    shipped_examples = grammar_type.get("examples") or [grammar_type["example"]]
    # A few spare exercises in the same call make up for what the verdict throws out.
    bestellt = count + max(1, round(count * _SPARE_SHARE))
    plan = item_plan(bestellt, kinds)
    # No target language, the exercise sentences stay in the source language.
    user_msg = f"Sources:\n\n{ctx.context}"

    def messages_for(wanted: list[str]) -> list[dict]:
        prompt = (
            _build_prompt(grammar_type, target_form, shipped_examples, wanted)
            + adaptive_suffix + title_avoidance + coverage + COMPACT_JSON_RULE
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
        response = create_logged(client, endpoint="grammatik", model=model, messages=messages_for(wanted),
                                 temperature=0.6, max_tokens=exercise_max_tokens(bestellt))
        data = loads_entries(_clean_llm_json(response.choices[0].message.content or ""), "exercises")
        exercises = list(data.get("exercises") or [])[:bestellt]
        seen_exercises += len(exercises)
        fresh, fresh_claims = _build_items(exercises, locale, shipped_examples, target_form)
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
            # The instruction is picked once here, kept items only, so a
            # retried duplicate keeps matching its earlier key above.
            anweisung = task_line(kind, locale, target_form)
            item["front"] = (f"**{anweisung}**\n\n{item['front']}" if item["front"]
                             else f"**{anweisung}**")
            items.append(item)
            claims.append(claim)
        if len(items) >= bestellt:
            break
        logger.info("KI Tutor: Grammatik-Wurf {} ergab {}/{} Aufgaben",
                    attempt + 1, len(items), count)
    items, claims = items[:bestellt], claims[:bestellt]

    # One verdict call for the whole throw, catches what no code filter can: a
    # sentence that only reads wrong once the answer sits in it.
    _, falsch = _VERDICT_LABELS.get(locale, _VERDICT_LABELS["en"])
    wrong_on_purpose = [item.get("_kind") == "statement" and item.get("back") == falsch
                        for item in items]
    # The gap as shown, the instruction above it left off.
    gaps = [(item["front"].rsplit("\n\n", 1)[-1], item["back"])
            if item.get("_kind") == "cloze" else None for item in items]
    ok = verdicts(client, model, claims, target_form, grammar_type["rule"],
                  wrong_on_purpose, gaps)
    items = [item for item, usable in zip(items, ok) if usable][:count]
    claims = [claim for claim, usable in zip(claims, ok) if usable][:count]

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


def _shape_block(examples: list[dict]) -> str:
    """One worked pair to copy, or several equally correct musterwege."""
    if len(examples) <= 1:
        example = examples[0] if examples else {"before": "", "after": ""}
        return (
            "SHAPE TO COPY. Every exercise looks exactly like this pair:\n"
            f'  before: "{example["before"]}"\n'
            f'  after:  "{example["after"]}"\n\n'
        )
    numbered = "\n".join(
        f'  {i}. before: "{ex["before"]}"\n     after:  "{ex["after"]}"'
        for i, ex in enumerate(examples, start=1)
    )
    return (
        "SHAPE TO COPY. These are DIFFERENT constructions for the SAME "
        "transformation rule, every exercise looks exactly like ONE of them:\n"
        f"{numbered}\n\n"
        "Pick whichever shape fits the sentence for 'after'. When another shape "
        "above also fits the same sentence, put it in 'also_ok' too, worded the "
        "same way that shape is.\n\n"
    )


def _build_prompt(grammar_type: dict, target_form: str, examples: list[dict],
                  plan: list) -> str:
    # The pattern pair goes along as a form to imitate, a bare rule has no effect.
    shape = (
        _shape_block(examples) +
        "NOT like these, they are all wrong here:\n"
        '  "Was bedeutet wissenschaftliches Arbeiten?"  (a question, cannot be transformed)\n'
        '  "Nennen Sie drei Beispiele."                 (an instruction, not a statement)\n'
        '  "Wissenschaftliches Arbeiten"                (not a sentence)\n\n'
        # A separate example for the gap with its base form named.
        "GAP TO COPY, for kind \"cloze\":\n"
        '  sentence "Der Bericht wird von Jasmin geschrieben.", form_span "wird", '
        'base_form "werden"\n\n'
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
        "- cloze starts from a COMPLETE, correct sentence that shows the target form, "
        "with NO gap in it. 'form_span' is the part of that sentence which carries "
        "the form, copied out of it character for character, at most three words. "
        "The software cuts the gap, not you. Whatever stands in 'form_span' is the "
        "correct answer, so the sentence has to read correctly with it. 'form_span' "
        "holds ONLY words the learner can work out from 'base_form' and the target "
        "form. Every other word stays in the sentence, the noun after an inflected "
        "adjective too:\n"
        '    sentence "Wir fahren mit dem neuen Zug nach Hamburg.", '
        'form_span "neuen", base_form "neu"\n'
        "  The learner "
        "TYPES the answer. 'base_form' is REQUIRED, never left out and never empty: "
        "the dictionary/infinitive form of the word in 'form_span', shown next to "
        "the gap as the learner's only hint at what to inflect. It is almost always "
        "DIFFERENT from 'form_span', copying 'form_span' into it is wrong:\n"
        '    sentence "Die Messwerte wurden vom Server gespeichert.", '
        'form_span "wurden", base_form "werden"\n'
        "  'also_ok' lists other fillings of the SAME gap that are just as correct, "
        "up to two, worked out the same way as 'also_ok' for transform above.\n"
        "- choice: the SAME shape as transform, a 'before' and its correct 'after', "
        "but the learner PICKS 'after' from three complete sentences instead of "
        "typing it, so 'after' is NEVER shown with a gap. 'wrong' lists exactly TWO "
        "other complete transformations of the SAME 'before', each one wrong in "
        "exactly ONE detail of the target form, a plausible learner mistake, never a "
        "nonsense sentence. The two must differ from each other and from 'after':\n"
        '    before "Der Dozent prüft die Quelle genau.", after "Die Quelle wird vom '
        'Dozenten genau geprüft.", wrong ["Die Quelle wurde vom Dozenten genau geprüft.", '
        '"Die Quelle ist vom Dozenten genau geprüft."]\n'
        "- statement: a sentence that either shows the target form correctly or gets it "
        "wrong. 'answer' is true when it is correct. About half of them are false, and a "
        "false one is wrong in exactly ONE detail of the TARGET FORM ITSELF, never a "
        "different rule elsewhere in the sentence. If the target form were Konjunktiv "
        "II, the error sits in the Konjunktiv-II form, never in the word order. If it "
        "were Adjektivdeklination, the error sits in the ending, never in the "
        "article's gender. A learner who already masters the target form must be able "
        "to spot the error from that form alone. It is a sentence that USES the form, "
        "never a claim ABOUT grammar. Wrong here, it states a rule instead of "
        'practising it: "Das Verb steht im Relativsatz immer am Ende."\n'
        "  A sentence marked 'answer': true must be exactly how a native speaker "
        "would phrase it, never a plausible-looking guess: a wrong preposition or a "
        "wrong fixed verb-preposition pairing makes it false, even when only one "
        "word is off, e.g. 'sich bemühen zur Verlängerung' is wrong, only 'sich "
        "bemühen um die Verlängerung' is correct. Its 'explanation' names only the "
        "category the target form itself is, never a different, more impressive-"
        "sounding one: a fixed verb + preposition + noun is a Präpositionalobjekt, "
        "not a Finalsatz, unless it is actually built with 'um ... zu' plus "
        "infinitive or 'damit'.\n\n"
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
        "- Every sentence is complete in meaning for someone who never read the source. "
        "When you shorten a fact, a noun that needs to say of what or of whom keeps "
        "that part:\n"
        '    source "Seitdem die Brücke gebaut wurde, wächst der Handel." -> '
        '"Seit dem Bau der Brücke wächst der Handel."\n'
        "- Every sentence is a STATEMENT. Never a question, never an instruction to the "
        "learner, never a bare phrase.\n"
        "- Every 'before' MUST be a valid input for the transformation rule above. "
        "If the rule needs a modal verb, every sentence contains one.\n"
        "- 'before' must be in the SAME tense as 'before' in the shape example(s) "
        "above, not merely a grammatically valid input. If the shape's 'before' is "
        "in the present tense, every new 'before' is in the present tense too, never "
        "a past-tense fact from the source dressed up as if it still held now. "
        "Drifting the tense changes what actually happened and makes 'after' claim "
        "something the source never said.\n"
        "- Every noun you invent, in 'before', 'after' and 'wrong' alike, keeps its "
        "OWN grammatical gender, not the gender of a similar-sounding noun elsewhere "
        "in the exercise. Check it before contracting a preposition with an article "
        "(zum, zur, im, am, beim, ...): 'zur besseren Verständnis des Textes' is "
        "wrong, because 'Verständnis' is neuter, only 'zum besseren Verständnis des "
        "Textes' is correct.\n"
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
        '    before "Er beruhigt sich. Er hört Musik.", '
        'after "Er beruhigt sich, indem er Musik hört.", '
        'also_ok ["Er beruhigt sich dadurch, dass er Musik hört."]\n'
        "  Typical cases are a different word order, an equally correct alternative "
        "form, an optional part left out, and a different construction that performs "
        "the same transformation, such as another connector the rule allows. The "
        "learner's answer is marked by "
        "comparing it against 'after' and this list and nothing else, so a valid "
        "wording missing here is marked as a mistake. An empty list is the rare "
        "exception, only when no other correct wording exists at all.\n"
        # No length rule, the difficulty comes from the language level alone.
        "- Every sentence is exactly ONE sentence.\n"
        "- The people in the sentences are CONCRETE and fit the setting of the source: a "
        "role ('die Professorin', 'der Dozent', 'die Mitarbeiterin', 'der Student') or an "
        "invented first name ('Ali', 'Jasmin', 'Petra', 'Max'), matching the output language. "
        "Never a vague subject such as 'das Team', 'die Person', 'jemand' or 'man', and vary "
        "the people from one exercise to the next. Never use the name of a real person "
        "mentioned in the source.\n"
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


def is_usable_cloze(sentence: str, form_span: str) -> bool:
    """Whether sentence and form carrier make a solvable gap."""
    return cut_gap(sentence, form_span) is not None


def _build_items(exercises: list[dict], locale: str, examples: list[dict],
                 target_form: str) -> tuple[list[dict], list[str]]:
    """The exercise rows plus the text the source is matched by."""
    yes, no = _VERDICT_LABELS.get(locale, _VERDICT_LABELS["en"])
    # Every stored musterweg is off limits, not only the one shown to the learner.
    banned = set()
    for ex in examples:
        banned.add(normalize(ex.get("before") or ""))
        banned.add(normalize(ex.get("after") or ""))
    banned.discard("")
    # The learner's hint always shows the first musterweg.
    primary = examples[0] if examples else {"before": "", "after": ""}
    items, claims = [], []
    for ex in exercises:
        kind = (ex.get("kind") or "transform").strip().lower()
        built = _build_one(ex, kind, yes, no, primary)
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


def _collect_alt_fillings(span: str, also_ok) -> dict:
    """Extra valid fillings of the same gap, they carry the check without a model."""
    accepts, seen = [], {normalize(span)}
    for alt in (also_ok or [])[:3]:
        alt = str(alt).strip()
        if not alt or normalize(alt) in seen:
            continue
        seen.add(normalize(alt))
        accepts.append(alt)
    return {"accepts": accepts} if accepts else {}


def _collect_wrong_transforms(before: str, after: str, wrong) -> list[str]:
    """Up to two distinct, usable incorrect transformations of 'before', fewer if the model repeats itself."""
    seen = {normalize(after)}
    out = []
    for w in (wrong or [])[:2]:
        w = str(w).strip()
        if not is_usable_pair(before, w) or normalize(w) in seen:
            continue
        seen.add(normalize(w))
        out.append(w)
    return out


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
        base_form = (ex.get("base_form") or "").strip()
        # The hint is the whole point of a gap, one without it is not finished.
        if not base_form or not is_usable_cloze(sentence, span):
            return None
        extras = _collect_alt_fillings(span, ex.get("also_ok"))
        gapped = cut_gap(sentence, span)
        # The base form sits right after the gap, a hint a click could otherwise skip.
        if normalize(base_form) != normalize(span):
            gapped = gapped.replace(GAP, f"{GAP} ({base_form})", 1)
        return {"front": gapped, "back": span, "extras": extras}, sentence

    if kind == "choice":
        before = (ex.get("before") or "").strip()
        after = (ex.get("after") or "").strip()
        if not is_usable_pair(before, after):
            return None
        # Two distinct wrong transformations are the whole point, fewer means no real choice.
        wrong = _collect_wrong_transforms(before, after, ex.get("wrong"))
        if len(wrong) < 2:
            return None
        # The correct option sits first, the frontend shuffles before showing it.
        return {"front": before, "back": after,
                "options": [after] + wrong, "correct_idx": 0}, after

    if kind == "statement":
        text = (ex.get("statement") or "").strip()
        verdict = ex.get("answer")
        if not is_usable_statement(text, verdict):
            return None
        return {"front": text, "back": yes if verdict else no,
                "options": [yes, no], "correct_idx": 0 if verdict else 1}, text

    # A kind that does not exist, guessing would be worse than leaving it out.
    return None
