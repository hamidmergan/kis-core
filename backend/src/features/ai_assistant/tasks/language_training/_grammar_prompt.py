"""The system prompt of the grammar exercise: answer shape, worked pair and the rules."""

from src.features.ai_assistant.tasks.language_training._attribution import PAGE_RULE
from src.features.ai_assistant.tasks.language_training._plan import plan_sentence


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
