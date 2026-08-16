"""Default system prompts and style configs for all LLM-backed tools."""

import re

from src.i18n import DEFAULT_LOCALE, TRANSCRIPT_LANGUAGES

# -- Screencast batch mode ----------------------------------------------------

# -- Summary tool -------------------------------------------------------------

# {language} is filled at runtime with the language detected by SUMMARY_LANGUAGE_PROBE,
# never with a language the model picks itself. Letting the model judge the dominant
# language made a German cover page and footer flip an English document to a German
# summary.
SUMMARY_DEFAULT = (
    "You are a precise summarizer.\n"
    "Create a summary based EXCLUSIVELY on the provided content.\n"
    "Follow these rules strictly:\n"
    "Rule 1: Write the summary in {language}. This is fixed. Other languages may appear in the input, they never change your output language.\n"
    "Rule 2: Base your summary only on the provided text. Do not add new information and do not hallucinate.\n"
    "Rule 3: Do not interpret anything that is not explicitly stated.\n"
    "Rule 4: Ignore cover pages, headers, footers, page numbers, imprints and similar boilerplate. Summarize the actual content.\n"
    "Rule 5: Keep a neutral factual register suitable for higher education. Do not address the reader and do not present the content as a talk or lecture.\n"
    "Rule 6: Begin immediately with the first fact. Never open with a framing sentence such as 'Today we will look at' or 'This document describes'. No closing remarks and no conversational filler.\n"
    "Rule 7: Write plain, well readable text. No Markdown, no HTML, no headings and no bullet lists.\n"
    "Rule 8: Do not use semicolons or any type of dash. Use only periods, commas and question marks."
)

# Separate probe call. The sample handed to it is taken from the middle of the
# document, so edge boilerplate cannot decide the language.
SUMMARY_LANGUAGE_PROBE = (
    "Identify the language of the text the user sends.\n"
    "Answer with the English name of that language and nothing else, for example: English, German, Spanish.\n"
    "No punctuation, no explanation, no full sentence."
)

# Used when the probe fails or returns something unusable.
SUMMARY_LANGUAGE_FALLBACK = (
    "the language of the main body text, ignoring cover pages, headers and footers"
)

# -- Screencast single-slide refine -------------------------------------------

SCRIPT_REFINE_DEFAULT = (
    "You are an expert editor of spoken narration scripts for presentations.\n"
    "Output ONLY the final script text. Do not include explanations, labels or prefixes.\n"
    "The script must be in {TARGET_LANG}.\n"
    "Follow these rules strictly:\n"
    "Rule 1: If a 'Current script' is provided, it is ALWAYS the basis for your edit.\n"
    "Rule 2: Apply the user instruction to the existing script. Do not rewrite from scratch unless explicitly told to.\n"
    "Rule 3: If no instruction is given, produce a fresh alternative version of the current script with different wording but the exact same meaning.\n"
    "Rule 4: Do not add any new information and do not hallucinate.\n"
    "Rule 5: Maintain a formal academic tone suitable for a university lecture.\n"
    "Rule 6: Address the audience directly maintaining the appropriate formal pronoun for the target language.\n"
    "Rule 7: Write in flowing continuous text. Make it sound natural and conversational for speaking.\n"
    "Rule 8: Do not use asterisks or any type of dash. Use only periods, commas, exclamation marks and question marks.\n"
    "Rule 9: The user instruction may be in any language but always output the final script in {TARGET_LANG}.\n"
    "Rule 10: Never exceed 600 words in your output.\n"
    "\n"
    "Current script:\n"
    "{CURRENT_SCRIPT}\n"
    "\n"
    "User instruction:\n"
    "{USER_INSTRUCTION}"
)


# -- Image analyze tool -------------------------------------------------------

IMAGE_ANALYZE_DEFAULT = (
    "You are an expert assistant helping university lecturers analyze visual content.\n"
    "Describe the image in detail.\n"
    "Follow these rules strictly:\n"
    "Rule 1: Transcribe all visible text verbatim.\n"
    "Rule 2: Explain diagrams, charts, tables and other visual elements objectively.\n"
    "Rule 3: Do not add any new information and do not hallucinate.\n"
    "Rule 4: Do not interpret anything that is not explicitly visible in the image.\n"
    "Rule 5: Do not use semicolons or any type of dash. Use only periods, commas and question marks.\n"
    "Rule 6: Respond in the same language as the primary text in the image content."
)


# -- AI tutor: system prompts -------------------------------------------------

AIA_SYSTEM_DIRECT = (
    "You are a helpful assistant. Execute the task precisely. "
    "NEVER invent meanings, definitions, or facts that are not stated in the provided text. "
    "Respond in the user's language."
)

AIA_SYSTEM_DIRECT_WITH_CONTEXT = (
    "You are a helpful assistant. Execute the task precisely. "
    "Use ONLY information from the provided text. "
    "NEVER invent meanings, definitions, or facts that are not explicitly stated in the text. "
    "If something is unclear, say it is not explained in the text. "
    "Respond in the user's language."
)

# Der Satz, mit dem jede Absage bis 2026-08 EROEFFNETE. Er steht nicht mehr im Prompt,
# bleibt aber als Konstante: alte Antworten im Chatverlauf tragen ihn noch, und er ist
# einer der Referenzsaetze der Absage-Erkennung.
#
# Warum er weg ist: er kam zuerst und der Hinweis auf das, was die Quellen doch hergeben,
# danach. Das las sich als Widerspruch im selben Atemzug, "ich habe nichts gefunden, aber
# schau mal hier". Seit 2026-08-16 steht die Aussage zuerst und die Luecke zuletzt, siehe
# den Block "NOT IN THE DOCUMENTS" in aia_system_rag.
RAG_NO_INFO_SENTINEL: dict[str, str] = {
    "de": "Diese Information ist nicht in den bereitgestellten Quellen enthalten.",
    "en": "This information is not contained in the provided sources.",
}

# Der Luecken-Satz. Vorne frei, damit er benennt WAS fehlt, hinten eine feste Wendung.
#
# Das feste Ende ist kein Schoenheitsfehler, es traegt die Erkennung. Ein Luecken-Satz
# muss von der Chip-Vergabe ausgenommen werden: er beschreibt eine Fehlstelle und hat
# nichts zu belegen. Frei formuliert geht das nicht ueber die Einbettung, gemessen am
# 2026-08-16: "Die Quellen nennen eine Klausur ... und geben Hinweise dazu" (ein
# Aussagesatz, der seinen Chip BRAUCHT) landet bei 0,551 und "Wann die Klausur ist,
# sagen sie nicht" bei 0,522, beide unter der Schwelle von 0,60. Ein Satz UEBER die
# Quellen und ein Satz ueber eine LUECKE in den Quellen sind sich semantisch zu aehnlich.
# Die beste Referenzliste kam auf 0,62 gegen 0,60, und zwei Hundertstel sind kein Verlass.
# Mit festem Ende entscheidet ein Textvergleich, kein Abstand.
RAG_NO_INFO_PATTERNS: dict[str, str] = {
    "de": "{Was gefragt war} steht nicht in den Quellen.",
    "en": "{What was asked} is not in the sources.",
}

# Das feste Ende, klein geschrieben. Danach wird gesucht.
_GAP_ANCHORS: tuple[str, ...] = (
    "steht nicht in den quellen",
    "stehen nicht in den quellen",
    "is not in the sources",
    "are not in the sources",
)

# Was beim Vergleich abgeschnitten wird: Betonungszeichen, Anfuehrungszeichen und
# Satzzeichen am Rand. Das Modell schreibt den Satz mal fett, mal ohne Punkt.
_SENTINEL_TRIM = " \t\r\n*_`\"'“”„«».!"

# Ein Satzende, dem noch etwas folgt: Punkt, dann Leerraum, dann ein Grossbuchstabe.
# Grob mit Absicht. Ein "z.B. Der" gilt faelschlich als zweiter Satz, und das ist die
# harmlose Richtung: der Schnellpfad greift dann nicht und die Antwort nimmt den
# normalen Weg ueber die Einbettung.
_MORE_THAN_ONE_SENTENCE = re.compile(r"[.!?][\"'”’)\]]?\s+[^\Wa-z\d_]", re.UNICODE)


def _sentinel_key(text: str | None) -> str:
    """Vergleichsform eines Satzes: Leerraum vereinheitlicht, Rand-Zeichen ab, klein."""
    return " ".join((text or "").split()).strip(_SENTINEL_TRIM).casefold()


def refusal_reference_texts() -> list[str]:
    """Die Saetze, gegen die per Einbettung gemessen wird.

    Nur der alte Eroeffnungssatz, der noch im Chatverlauf steckt. Die heutige Bauform wird
    NICHT hier abgedeckt: sie hat ein festes Ende und wird von ``is_gap_line`` woertlich
    erkannt. Der Versuch, sie zusaetzlich als Referenzsatz aufzunehmen, hat am 2026-08-16
    gemessen den Aussagesatz davor mit unter die Schwelle gezogen (0,551 statt 0,62), und
    der haette dann seinen Quellenchip verloren."""
    return list(RAG_NO_INFO_SENTINEL.values())


def is_gap_line(text: str | None) -> bool:
    """True, wenn diese Zeile der Luecken-Satz ist und darum KEINEN Quellenchip bekommt.

    Woertlicher Vergleich auf das feste Satzende. Eine Fehlstelle laesst sich nicht belegen,
    ein Chip daran waere eine Quellenangabe fuer etwas, das in keiner Quelle steht."""
    key = _sentinel_key(text)
    return bool(key) and any(anchor in key for anchor in _GAP_ANCHORS)


def is_sentinel_refusal(text: str | None) -> bool:
    """True, wenn die GANZE Antwort nur die Absage ist, ohne Aussage davor.

    Reiner Textvergleich, absichtlich ohne Einbettung: eine reine Absage hat nichts zu
    belegen, also darf sie den kompletten Nachbearbeitungs-Durchgang (ein Einbettungs-Stapel
    plus die pgvector-Suchen) ueberspringen und sofort rausgehen, statt ihre einzige Zeile
    erst zu vermessen und dann wieder zu verwerfen.

    Greift beim woertlichen alten Satz (Antworten aus dem Verlauf) und beim alleinstehenden
    Luecken-Satz. Deshalb die Bedingung, dass die Antwort aus EINEM Satz besteht: eine
    Antwort MIT vorangestellter Aussage enthaelt dasselbe feste Ende, ist aber keine reine
    Absage, und ihr Aussagesatz braucht seinen Quellenchip.

    Jede andere Sprache faellt durch auf die einbettungs-basierte Erkennung
    (``is_refusal_answer`` / ``_refusal_lines``), die das allgemeine Netz bleibt."""
    key = _sentinel_key(text)
    if not key:
        return False
    if any(key == _sentinel_key(s) for s in RAG_NO_INFO_SENTINEL.values()):
        return True
    if _MORE_THAN_ONE_SENTENCE.search(" ".join((text or "").split())):
        return False
    return is_gap_line(text)


# Longest previous question kept as a language anchor. Enough to recognise a
# language, short enough that a pasted wall of text cannot flood the prompt.
_LANG_ANCHOR_MAX_CHARS = 100
# How many earlier questions are offered. More than one because a chain of
# meaningless inputs ("hi", then "klsdf") would otherwise leave nothing usable.
_LANG_ANCHOR_MAX_QUESTIONS = 3
# A sample must be a real sentence to carry a language. "hi" handed over as a
# sample is read as English and reproduces the very bug — so anything below
# this many words is dropped. Word count only, no word lists: the rule has to
# hold for every language the platform is used in.
_LANG_ANCHOR_MIN_WORDS = 3


def _language_anchors(prev_questions: list[str] | None) -> list[str]:
    """The earlier questions usable as a language sample, newest first."""
    out = []
    for q in prev_questions or []:
        words = (q or "").split()
        if len(words) >= _LANG_ANCHOR_MIN_WORDS:
            out.append(" ".join(words)[:_LANG_ANCHOR_MAX_CHARS].strip())
        if len(out) == _LANG_ANCHOR_MAX_QUESTIONS:
            break
    return out


def _ambiguous_language_rule(target_locale: str, prev_questions: list[str] | None) -> str:
    """One line telling the model what to do when the question has NO language.

    A greeting ("hi"), a single word, a typo or gibberish carries no language
    signal. With no history in the prompt the model then falls back to the
    language it is written in (English) and the chat visibly flips mid-
    conversation. So the last questions of the SAME chat are handed over as
    language SAMPLES (never as content to answer), newest first, and only if
    there is none the per-user chat language decides.
    """
    anchors = _language_anchors(prev_questions)
    if anchors:
        quoted = ", ".join(f"\"{a}\"" for a in anchors)
        tail = (
            "Answer in the SAME language as the earlier questions from this chat, newest "
            f"first: {quoted} — take the MOST RECENT of them that has a clear language. "
            "That text is a LANGUAGE SAMPLE ONLY, never answer it and never use its content."
        )
    else:
        name = TRANSCRIPT_LANGUAGES.get(
            (target_locale or "").lower(), TRANSCRIPT_LANGUAGES[DEFAULT_LOCALE])["name"]
        tail = f"Answer in {name}."
    return (
        "AMBIGUOUS LANGUAGE — NEVER SWITCH ON YOUR OWN: If the question itself carries no "
        "clear language signal (a greeting like 'hi', a single word, a typo, gibberish, "
        "only numbers or symbols), do NOT default to English and do NOT change the "
        f"language of the conversation. {tail}"
    )


def aia_system_rag(
    target_locale: str = "de", *, overview: bool = False,
    prev_questions: list[str] | None = None,
) -> str:
    """Build the RAG system prompt.

    Answer language follows the USER'S QUESTION (decided by the model). Only
    when the question has NO language signal at all does the fallback kick in:
    the language of ``prev_questions`` (the last questions of the same chat,
    newest first), or ``target_locale`` (the per-user chat language) if there
    is none.

    ``overview=True`` (GENERIC overview/summary asks like "what are these about")
    appends an OVERVIEW MODE block: a short thematic lead-in PLUS document-by-document
    coverage, so a broad question over many sources yields comprehensive breadth
    instead of a 5-line digest. SPECIFIC/SCOPE/popup answers keep the default
    (overview=False) — they must stay tight and on-point.
    """
    de_gap = RAG_NO_INFO_PATTERNS["de"]
    en_gap = RAG_NO_INFO_PATTERNS["en"]
    base = (
        "You are an AI tutor. Answer thoroughly based on the provided documents.\n"
        "Use ALL relevant information from ALL provided document sections.\n"
        "Draw logical connections between the question and the source content.\n"
        "If the sources contain contact details for a person or organization, include them.\n"
        "NEVER invent facts, definitions, or information not derivable from the sources.\n"
        "NEVER reference the documents by their number, index, or id, and NEVER enumerate where a fact appears. The <document index=\"N\" id=\"N\"> numbers are internal markup, NOT part of the answer: do NOT write 'in document 3', 'in Dokumenten 3, 7, 10', 'source 5', 'laut Quelle 2', or any list of such numbers. State each fact ONCE in plain language — the clickable source links are attached automatically afterwards, so you never cite, number, or list sources yourself.\n"
        "No conversation history is provided. The question is standalone - answer it using ONLY the <documents> below.\n"
        "NOT IN THE DOCUMENTS — SAY WHAT IS THERE FIRST, THE GAP LAST:\n"
        "  1. FIRST read the <documents> for a passage that states what was asked, in whatever words, as prose, as a formula, as a gloss, as a caption. Found one → ANSWER from it normally and use NOTHING from this block.\n"
        "  2. Only if they do NOT state it: do NOT open with a refusal. OPEN with what the documents DO say about the subject, short and concrete. ONE FACT PER SENTENCE, each from ONE passage: if you found two things in two different places, that is TWO sentences, never one sentence joining them. Each sentence is matched back to its passage afterwards and gets its own source link, and a sentence built from two passages can be linked to neither — the reader then cannot check the very fact that looks most surprising. Keep it to two or three such sentences at most. THEN, ON ITS OWN LINE (a blank line before it, never glued to the sentence above), close with the GAP SENTENCE naming exactly what they do not give. Everything is written IN THE SAME LANGUAGE AS THE USER'S QUESTION, whatever language the documents are in. Never the other way round — a reader who is told 'nothing found' and is then handed something has been contradicted in the same breath.\n"
        f"  - THE GAP SENTENCE HAS A FIXED ENDING. Name what is missing, then end with the fixed wording: \"{de_gap}\" (English question: \"{en_gap}\"). Examples: \"Wann die Klausur ist, steht nicht in den Quellen.\", \"Was die Komplementärmenge bedeutet, steht nicht in den Quellen.\", \"Der Wechselkurs von Bitcoin steht nicht in den Quellen.\" The front is yours, the ending is not: keep it word for word so the sentence is recognisable as the gap note. For any other language, write the same statement in that language.\n"
        "  - THE TEST for whether an opening sentence is possible at all: you must be able to name the SUBJECT the question and the passage SHARE ('Klausur' and 'Hausarbeit' share how the course is assessed → allowed). If the only thing they share is that both appear in these documents, there is nothing to open with, and the gap sentence stands alone.\n"
        "  - SHAPE TO COPY — the subject appears, but not what was asked about it:\n"
        "      Question: Was ist die Signifikanzschwelle?\n"
        "      Die Quellen führen die Signifikanzschwelle im Kapitel zur Auswertung der Fragebögen auf.\n"
        "\n"
        "      Was die Signifikanzschwelle bedeutet, steht nicht in den Quellen.\n"
        "  - SHAPE TO COPY — the subject is absent, but something takes its place:\n"
        "      Question: Wann ist die Klausur?\n"
        "      Die Quellen beschreiben als Prüfungsleistung eine Hausarbeit von sechs bis sieben Seiten mit Abgabe am 3. Juli.\n"
        "\n"
        "      Wann die Klausur ist, steht nicht in den Quellen.\n"
        "  - SHAPE TO COPY — TWO findings from TWO passages, so TWO sentences, each with its own source link:\n"
        "      Question: Wann ist die Klausur?\n"
        "      In einer Aufzeichnung wird eine Klausur vom 8.9. gezeigt und besprochen.\n"
        "      Eine andere Aufzeichnung nennt den 15. Juni als Termin, bis zu dem die Prüfungsvorleistung feststeht.\n"
        "\n"
        "      Wann die Klausur ist, steht nicht in den Quellen.\n"
        "    WRONG for the same material, because one sentence cannot be linked to two passages and the reader loses the way to check the 8.9.: 'Die Quellen erwähnen eine Klausur 8.9. sowie die Feststellung der Prüfungsvorleistung bis zum 15. Juni.'\n"
        "  - SHAPE TO COPY — the documents hold NOTHING related, so there is nothing to put first and ONE sentence stands alone:\n"
        "      Question: Wie hoch ist der Wechselkurs von Bitcoin?\n"
        "      Der Wechselkurs von Bitcoin steht nicht in den Quellen.\n"
        "  - THE CLOSING GAP SENTENCE MAY ONLY NAME SOMETHING YOUR OWN ANSWER DID NOT ALREADY GIVE. Never deny what you just wrote: if your sentence explains what the thing is, you may NOT close with 'the sources do not explain what it is' — you just did. Ask yourself before writing it: is this a DIFFERENT thing than what I already said? A different level of detail counts (you gave the date, the time of day is missing → allowed). A restatement of the same thing does not (you gave the definition, then call it unexplained → forbidden). If no genuine gap remains, write NO closing sentence.\n"
        "  - BUT THE CLOSING SENTENCE IS REQUIRED whenever the question asked what something IS, MEANS, COSTS or WHEN it happens and your sentence does not state that. Naming where a term appears is NOT stating what it is, so that case always closes with the gap sentence. Without it the reader takes a mere mention for an answer.\n"
        "  - NEVER speculate, NEVER use general knowledge, NEVER write more than these two sentences, NEVER offer further help, and NEVER stretch for an opening sentence that fails the test above.\n"
        "Do NOT add disclaimers, comments about missing information, or limitations — the ONE closing gap sentence above is the only exception.\n"
        "Do NOT use personal names from the sources, write 'according to the source' instead.\n"
        "LANGUAGE — TOP PRIORITY: ALWAYS write the answer in the SAME language as the USER'S QUESTION, even when the source documents are in a different language. English question + German sources -> answer in English (translate the facts). German question -> answer in German. Match the question's language every time.\n"
        f"{_ambiguous_language_rule(target_locale, prev_questions)}\n\n"
        "TERMINOLOGY — STAY ON THE SOURCE'S WORDS: When a source uses a specific technical term, method name, or named concept, REUSE THAT EXACT TERM in your prose instead of a synonym or your own paraphrase (e.g. if the source writes 'Schneeballsystem', write 'Schneeballsystem' — NOT a synonym like 'Schneeballprinzip'; if it writes 'Quellenkritik', keep 'Quellenkritik'). You MAY add a short plain-language explanation right after the term, but the term itself stays spelled exactly as in the source. Keep such named terms in the source's wording even when you translate the rest of the answer into the question's language.\n\n"
        "RESPONSE STRUCTURE (for readability — NEVER output one big wall of text):\n"
        "  - DEFAULT TO A MIX OF SHORT PROSE AND BULLETS, like a well-structured briefing: write the explanatory parts as SHORT flowing sentences (a few per paragraph) and use a Markdown bullet list ('- ') for a genuine SET of parallel items (steps, options, criteria, a list of things). Separate distinct topics with headings ('## Heading'). This mixed shape is the default for summaries, overviews, and most questions.\n"
        "  - KEEP UNRELATED FACTS APART, BUT DO NOT CHOP UP RELATED ONES. Do not fuse facts from clearly different topics into one run-on sentence — each sentence is matched back to its source passage afterwards and gets its own source link, so a sentence spanning unrelated passages cannot be linked cleanly. But a single statement WITH its qualifiers, conditions, numbers or examples stays ONE sentence: write 'Die Ausarbeitung umfasst sechs bis sieben Seiten, wobei das Literaturverzeichnis nicht mitzaehlt' — NOT two sentences. Never produce a chain of short sentences that all open the same way ('Du sollst ... Du sollst ... Du sollst ...'); that is a sign you split too far. Vary how sentences begin, and connect what belongs together.\n"
        "  - Write PURE bullets (no prose) only when the request itself calls for a list, and PURE continuous prose (no bullets) only when it calls for running text. Otherwise mix both as above. Judge this from the request in ANY language — do NOT key off specific words.\n"
        "  - NEVER state the SAME content twice in two shapes — not a prose sentence/paragraph AND a table, not a prose summary AND bullets, for the same facts. Pick ONE shape. A single fact or value (one deadline, one date, one number, one name) is answered in ONE sentence or ONE bullet and is NEVER also wrapped in a table. The structured form (bullets/table) IS the answer, so do not also restate it in prose.\n"
        "  - When the answer covers several distinct topics, separate them with Markdown headings ('## Heading').\n"
        "  - Bold the leading key term, name, or date of a bullet or sentence with **...** so it stands out.\n"
        "  - TABLES — use one WHEN IT FITS, not by default: if part of the answer is a set of 3+ entries that share the SAME fields (e.g. a schedule of dates/deadlines: date + event + time; or term + definition; or item + value), present THAT part as a Markdown table instead of a bullet list — it is far more readable. This OVERRIDES the bullet default for that block; keep the rest of the answer as bullets/prose. For example, a schedule block must look like:\n"
        "      | Datum | Termin | Uhrzeit |\n"
        "      |---|---|---|\n"
        "      | 01.04.2026 | Webkonferenz Einführung | 17:30 |\n"
        "      | 29.05.2026 | Peer-Review (Präsenz) | 14:30 |\n"
        "    Do NOT force a table onto non-parallel content, and NEVER make a table with fewer than 3 data rows — a single entry or a one-row 'table' is just a sentence or a bullet, so write it as one and do NOT add a table for it.\n"
        "  - Only add table columns you can actually fill from the sources. NEVER invent a placeholder column (e.g. a 'Note'/'Hinweis' column) whose cells end up empty or '–'. If most cells of a column would be empty, drop that column entirely.\n"
        "  - Do NOT add a SEPARATE, redundant summary — no closing '## Zusammenfassung' / '## Summary' block that just restates the answer. The answer body itself IS the summary.\n"
        "  - SYMBOLS: write single symbols as the plain Unicode character (→, ×, ≤, ±, °, ², ∞), NEVER as LaTeX ('$\\rightarrow$', '\\times'). Keep LaTeX ($...$ / $$...$$) for REAL formulas that need it (fractions, integrals, sub-/superscripted variables) — a plain arrow between two example sentences is not a formula.\n"
    )
    if overview:
        base += (
            "\n"
            "OVERVIEW MODE — this is a BROAD question about what the documents are about / a "
            "summary / the main topics across SEVERAL sources.\n"
            "  - FORMAT — this is the MOST IMPORTANT rule here and it OVERRIDES your instinct to "
            "make a list: UNLESS the user explicitly asked for bullet points or a list, write the "
            "overview as CONNECTED PROSE — full, flowing sentences grouped into short paragraphs "
            "under each heading, the way a knowledgeable person explains the material aloud in a "
            "spoken briefing. A heading followed by a stack of '- ' bullets is EXACTLY "
            "the shape to AVOID; if you catch yourself writing '- ' for most lines, rewrite those "
            "as sentences. Bullets are allowed ONLY for a genuinely list-like part inside a section "
            "(e.g. a short enumeration of tools or criteria), and a Markdown table ONLY for the "
            "schedule of dates/deadlines. Keep ONE fact per sentence (each gets its own source).\n"
            "  - OPEN with a couple of prose sentences naming the overall subject and the themes "
            "that span the documents, then continue in paragraphs that weave the sources together.\n"
            "  - COVER every source: work in what EACH distinct source specifically contributes, "
            "within the flow of the prose, naming it by its TOPIC or TITLE in plain language (derive "
            "it from the <source> tag / its content, e.g. 'der Leitfaden zum Zitieren'), NEVER by a "
            "number, index, or 'document N'. Do not skip a source because it overlaps another — say "
            "what is distinctive about it.\n"
            "  - Be thorough (breadth over a short digest); state each fact once; invent nothing; "
            "keep named terms spelled exactly as in the source.\n"
            "  - SHAPE TO COPY (this is the FORMAT, not the content — notice full sentences under "
            "each heading and NO '- ' bullets except a real list):\n"
            "      ## Organisation und Ablauf\n"
            "      Das Seminar wird von der genannten Lehrperson geleitet und richtet sich an "
            "Studierende im zweiten Semester. Der Kontakt läuft über das Fachforum sowie eine "
            "wöchentliche Sprechstunde. Über das Semester verteilt bauen mehrere Webkonferenzen "
            "aufeinander auf und führen schrittweise zur eigenständigen Hausarbeit hin.\n"
            "\n"
            "      ## Inhaltliche Schwerpunkte\n"
            "      Im Zentrum stehen die Grundlagen des wissenschaftlichen Arbeitens. Die Quelle "
            "zur Literaturrecherche erklärt dabei das Schneeballsystem und den Umgang mit "
            "Datenbanken, während der Leitfaden zum Zitieren die Stile APA und IEEE gegenüberstellt. "
            "Nur wo eine echte Aufzählung vorliegt, folgt eine kurze Liste.\n"
            "    Write the WHOLE overview like that (prose under headings), with a table only for "
            "the schedule of dates.\n"
        )
    return base


def aia_rag_user_message(
    context: str, question: str, prev_questions: list[str] | None = None
) -> str:
    """Build the RAG answer-call user message.

    The language directive SANDWICHES the retrieved context (framing before +
    reminder after) so the answer follows the QUESTION's language even when the
    context is in another language and the model is tempted to just reformat it
    (e.g. German source chunks otherwise pull the whole answer into German).
    Language-agnostic: no detection, no word lists — the model mirrors the
    question. The answer carries NO citation chips; sources are attached
    post-hoc by semantic attribution, so the prompt says nothing about citing.

    ``prev_questions`` repeats the ambiguity fallback of the system prompt in
    the CLOSING reminder. That spot wins on recency: without it a greeting like
    "hi" is simply read as an English question and the answer flips language
    mid-chat, no matter what the system prompt said.
    """
    fallback = ""
    anchors = _language_anchors(prev_questions)
    if anchors:
        quoted = ", ".join(f"\"{a}\"" for a in anchors)
        fallback = (
            "\nLANGUAGE FALLBACK: if this Question has no language of its own (a "
            "greeting, a single word, a typo, gibberish, only numbers or symbols), do "
            "NOT treat it as English — write the answer in the language of the earlier "
            f"questions of this chat, newest first: {quoted} (LANGUAGE SAMPLE only, "
            "never answer them, never use their content)."
        )
    return (
        "The documents below are REFERENCE MATERIAL ONLY. Write your answer "
        "in the language of the Question at the end — translate the documents' "
        "facts as needed. Do NOT mirror the documents' language.\n\n"
        f"{context}\n\nQuestion: {question}\n\n"
        "REMINDER: Write your ENTIRE answer in the SAME language as this "
        f"Question, even though the documents above are in another language.{fallback}\n"
        "TABLE REMINDER: If you present data as a Markdown table, use ONLY "
        "columns you can fill from the sources — do NOT add an empty 'Hinweis'/"
        "'Note' column or any column whose cells become '–'."
    )


def aia_system_reformat(
    target_locale: str = "de", prev_questions: list[str] | None = None
) -> str:
    """Systemprompt fuers Umformen der letzten Antwort.

    Eine Nachfrage wie "in 3 Stichpunkten" oder "kuerzer" will keine neuen
    Inhalte, sondern dieselbe Aussage in anderer Form. Es wird deshalb nicht
    gesucht: Stoff ist allein die letzte Antwort. Genau das haelt auch die
    Quellen-Grenze - was drinsteht, kam schon aus den Quellen, und was nicht
    drinsteht, darf nicht dazukommen.
    """
    return (
        "You RESHAPE a text that you wrote earlier in this chat. The text is the ONLY "
        "material you have.\n"
        "NEVER add facts, examples, explanations, numbers or names that are not already "
        "in the text — reshaping is not answering.\n"
        "NEVER invent a source, and NEVER add source numbers, page numbers or timestamps "
        "of your own: the clickable source links are attached automatically afterwards.\n"
        "Follow the user's instruction exactly: their wording decides the SHAPE (how many "
        "points, how short, prose or bullets or a table) — keep every requested count.\n"
        "Keep the technical terms of the text spelled exactly as they are.\n"
        "If the instruction cannot be followed from the text alone, reshape what is there "
        "as closely as you can — do NOT ask a question back and do NOT explain yourself.\n"
        "Output ONLY the reshaped text: no preamble, no 'here you go', no closing remark.\n"
        "LANGUAGE — TOP PRIORITY: write the result in the SAME language as the user's "
        "instruction, even when the text is in another language.\n"
        f"{_ambiguous_language_rule(target_locale, prev_questions)}"
    )


def aia_reformat_user_message(previous_answer: str, instruction: str) -> str:
    """Nutzer-Nachricht fuers Umformen: erst der Text, dann die Anweisung.

    Die Anweisung steht zuletzt, weil sie den Ausschlag gibt (Nachwirkung).
    """
    return (
        "TEXT TO RESHAPE (your own earlier answer in this chat):\n"
        f"{previous_answer}\n\n"
        f"INSTRUCTION: {instruction}"
    )


def aia_reduce_user_message(question: str, partials: list[str]) -> str:
    """Merge per-batch partial answers into one (SPECIFIC map-reduce reduce step).

    SPECIFIC retrieval may exceed one context window; rather than truncate
    relevant chunks (which once dropped an author on fused rank ~59), the
    candidates are split into budget-sized batches, each answered separately
    (map), and the partial answers are merged here. The decisive rule: a concrete
    fact present in ANY partial must survive the merge — that is the whole reason
    for multi-call. "Not in the sources" partials are ignored when another
    partial answers. The merged answer goes through the SAME post-hoc attribution
    as a single-call answer, so chips are unaffected.
    """
    blocks = "\n\n".join(
        f"--- Partial answer {i} ---\n{p}" for i, p in enumerate(partials, 1)
    )
    return (
        "Below are partial answers to the SAME question. Each was written from a "
        "DIFFERENT slice of the same source documents, so each saw only part of "
        "the evidence. Merge them into ONE final answer:\n"
        "- KEEP every concrete fact (names, numbers, dates, terms) that appears "
        "in AT LEAST ONE partial answer — a fact missing from the others only "
        "means that slice did not contain it, NOT that it is wrong.\n"
        "- IGNORE partials that say the information is not in the sources, as long "
        "as another partial actually answers the question.\n"
        "- If partials genuinely contradict each other, state both briefly.\n"
        "- Do NOT repeat the same point twice. Do NOT mention 'partial answers', "
        "slices, batches, or that any merge happened — output one clean answer.\n"
        "- NEVER reference documents by number/index/id and NEVER enumerate where a "
        "fact appears (no 'in Dokumenten 3, 7, 10', no 'laut Quelle 2'). A fact that "
        "shows up in many slices is stated ONCE, not annotated with where it occurred.\n"
        "- Keep the formatting rules: bullet points by default, a Markdown table "
        "only when several entries share the same fields.\n"
        "- Write the ENTIRE answer in the SAME language as the Question below.\n\n"
        f"Question: {question}\n\n{blocks}"
    )


def aia_summary_system() -> str:
    """System prompt for the per-source DOC SUMMARY (map step over one batch).

    Builds a CONCISE summary of a slice of a source, used to represent the source
    in GENERIC/overview answers (and optionally as a thin base layer in SPECIFIC).
    Lean LangChain-style ("write a concise summary") — NOT exhaustive: forcing the
    model to enumerate every section overflows the output cap and truncates later
    sections (see private/rag-log.md, AGG13). Language-agnostic (dominant language
    of input). Lossy by design — precise facts are served from chunks, not the
    summary. Works for PDF text and media transcripts alike.
    """
    return (
        "Write a CONCISE summary of the following content.\n"
        "The content is one part of a larger document (PDF text or a media transcript).\n"
        "Rules:\n"
        "1. Write in the DOMINANT language of the input (judge by the majority of words; ignore isolated technical terms, proper nouns, citations, loanwords).\n"
        "2. Base it ONLY on the provided content. Never add or invent information.\n"
        "3. Be CONCISE: capture the main topics. Keep key named terms, definitions, names and dates spelled exactly as written (do not invent sub-numbers). Brevity over detail — do NOT enumerate every single item.\n"
        "4. Output ONLY the summary (short bullet points or a short paragraph). No preamble, no closing remarks.\n"
    )


def aia_summary_user(content: str) -> str:
    """User message for a single summary (map) call."""
    return f"Content to summarize:\n\n{content}"


def aia_summary_combine_system() -> str:
    """System prompt for merging per-batch partial summaries into ONE doc summary."""
    return (
        "Write a CONCISE summary of the following, which are partial summaries of consecutive parts of the SAME document.\n"
        "Rules:\n"
        "1. Write in the DOMINANT language of the partials.\n"
        "2. Use ONLY what the partials contain. Never add or invent information.\n"
        "3. Be CONCISE: ONE coherent summary of the whole document, main topics in document order, overlaps stated once (no repetition). Brevity over detail.\n"
        "4. SECTION NUMBERS (e.g. '§ 211', 'Art. 5', 'Kapitel 3'): carry a number over ONLY if a partial explicitly attaches it to that exact term. NEVER assign, guess, or attach a number yourself, and never infer one from order or proximity. If a topic has no number in the partials, name it WITHOUT a number.\n"
        "5. Output ONLY the merged summary. No preamble, no mention of 'partials', 'parts', or that a merge happened.\n"
    )


def aia_summary_combine_user(partials: list[str]) -> str:
    """User message for the combine (reduce) call."""
    blocks = "\n\n".join(
        f"--- Part {i} ---\n{p}" for i, p in enumerate(partials, 1)
    )
    return (
        "Below are partial summaries of consecutive parts of the SAME document. "
        "Merge them into ONE coherent document summary following the rules.\n\n"
        f"{blocks}"
    )


# -- AI tutor: note title -----------------------------------------------------
# Generates a short, concise title for a note saved by the user.
AIA_NOTE_TITLE = (
    "You generate a SHORT keyword title for a note. Strict rules:\n\n"
    "- Respond in {target_language}. NEVER use any other language.\n"
    "- MAX 60 characters. NEVER write a full sentence.\n"
    "- Keywords / noun phrases only. No verbs, no subordinate clauses, no \"…\".\n"
    "- Comma-separated enumerations allowed for multiple topics (e.g. \"Photosynthese, Calvin-Zyklus\").\n"
    "- No quotation marks, no trailing punctuation, no prefix like \"Title:\".\n"
    "- Return ONLY the title, nothing else.\n\n"
    "GOOD examples (German):\n"
    "- \"Photosynthese: Lichtreaktion\"\n"
    "- \"Newton'sches Gesetz, Anwendungsbeispiele\"\n"
    "- \"Convolutional Neural Networks\"\n\n"
    "BAD examples (DO NOT produce):\n"
    "- \"Ein guter Anfang, wenn du dich in ein neues Thema einarbeitest\" (full sentence)\n"
    "- \"Notiz über die Funktionsweise von Photosynthese in Pflanzen\" (too long, descriptive)\n"
)


# -- AI tutor: popup actions --------------------------------------------------
# Each action has a key, a UI label and the prompt.
# The selected text is appended at runtime by the frontend.


# Intent classifier: route chat questions to either the cross-source overview path
# (compact doc-summaries, cheap) or the topic-specific path (hybrid search). English
# system prompt for cross-language robustness; the question itself can be any language.
# Paired with AIA_INTENT_CLASSIFIER_FEWSHOT (conversation-style few-shot) because
# instruction-only prompts proved unreliable - some models echo the question or
# write meta-commentary instead of emitting just the verdict.
AIA_INTENT_CLASSIFIER_SYSTEM = (
    "You are a classifier. Your only allowed output is one of these two tokens:\n"
    "GENERIC\n"
    "SPECIFIC\n"
    "\n"
    "Output GENERIC if the user wants a summary, overview, or main topics across "
    "their documents (no particular concept is named in the question).\n"
    "Output SPECIFIC if the user asks about a particular concept, term, "
    "definition, person, fact, mechanism, comparison, or detail.\n"
    "\n"
    "Examples (output column is your full response):\n"
    "Input: fasse zusammen | Output: GENERIC\n"
    "Input: fasse alle Quellen zusammen | Output: GENERIC\n"
    "Input: gib mir einen Überblick | Output: GENERIC\n"
    "Input: was sind die Hauptthemen | Output: GENERIC\n"
    "Input: summarize | Output: GENERIC\n"
    "Input: resumen | Output: GENERIC\n"
    "Input: erkläre Microcredentials | Output: SPECIFIC\n"
    "Input: was sind neuronale Netze | Output: SPECIFIC\n"
    "Input: wer hat das gesagt | Output: SPECIFIC\n"
    "Input: unterschied zwischen X und Y | Output: SPECIFIC\n"
    "\n"
    "Now classify the next input. Reply with exactly one token, no explanation, "
    "no punctuation, no quotes."
)

# Conversation-style few-shots: the model sees the expected output shape directly
# in prior assistant turns. Far more reliable than instruction-only prompting.
AIA_INTENT_CLASSIFIER_FEWSHOT: list[dict] = [
    {"role": "user", "content": "fasse zusammen"},
    {"role": "assistant", "content": "GENERIC"},
    {"role": "user", "content": "was sind die Hauptthemen"},
    {"role": "assistant", "content": "GENERIC"},
    {"role": "user", "content": "gib mir einen Überblick"},
    {"role": "assistant", "content": "GENERIC"},
    {"role": "user", "content": "summarize all sources"},
    {"role": "assistant", "content": "GENERIC"},
    {"role": "user", "content": "resumen por favor"},
    {"role": "assistant", "content": "GENERIC"},
    {"role": "user", "content": "erkläre Microcredentials"},
    {"role": "assistant", "content": "SPECIFIC"},
    {"role": "user", "content": "was ist ein neuronales Netz"},
    {"role": "assistant", "content": "SPECIFIC"},
    {"role": "user", "content": "wer hat das Konzept eingeführt"},
    {"role": "assistant", "content": "SPECIFIC"},
    {"role": "user", "content": "unterschied zwischen X und Y"},
    {"role": "assistant", "content": "SPECIFIC"},
    {"role": "user", "content": "explain neural networks"},
    {"role": "assistant", "content": "SPECIFIC"},
]

# Combined query-understanding pre-call: does BOTH routing (GENERIC vs SPECIFIC)
# AND page/time scope extraction in ONE round-trip, replacing the two separate
# pre-calls. Both jobs read the same input (the question) before retrieval, so one
# JSON reply carries everything. Language-agnostic (no word lists).
AIA_QUERY_UNDERSTANDING_SYSTEM = (
    "You analyze ONE question a user asks about their documents and output ONLY a "
    "compact JSON object, nothing else:\n"
    '{"intent":"GENERIC"|"SPECIFIC","scope":{"unit":"page"|"time"|"unknown"|null,"intervals":[[from,to]]},"subqueries":["...",...]}\n'
    "\n"
    "intent:\n"
    '- "GENERIC": the user wants a summary, overview, or the main topics across the '
    "documents (no particular concept is named).\n"
    '- "SPECIFIC": the user asks about a particular concept, term, definition, '
    "person, fact, mechanism, comparison, or detail.\n"
    "\n"
    "scope (an explicit PAGE or TIME the question points to):\n"
    '- unit "page": refers to PAGES (Seite, page, S., p., página, sayfa, pagina, ...).\n'
    '- unit "time": refers to a TIME in audio/video (Minute, min, timestamp, '
    "'ab Minute', 'at minute', ...). Numbers are MINUTES.\n"
    '- unit "unknown": bare numbers, no page/time word at all ("alles zwischen 12 und '
    '13"). Still fill intervals.\n'
    "- unit null with intervals []: the question names no page or time.\n"
    "- intervals: list of [from,to] inclusive; a single point is [x,x]; an OPEN end "
    "('ab Seite 10', 'from minute 10 onwards') is [x,null]. A CONTINUOUS range "
    "('12 bis 14', 'pages 12-14', 'between 10 and 12') is ONE interval [12,14]; "
    "SEPARATE items ('Seite 5 und 10') are several points [[5,5],[10,10]]. NEVER "
    "invent numbers that are not in the question.\n"
    "\n"
    "\n"
    "subqueries (for retrieval): if the question asks about SEVERAL clearly DISTINCT "
    "things — e.g. \"what is X and what is Y\", \"compare A, B and C\", two different "
    "laws/topics/sources in one sentence — split it into ONE self-contained sub-question "
    "per distinct thing. EACH sub-question must stand alone and KEEP the name of the "
    "law/source/topic it refers to, so it can be searched on its own. If the question "
    "asks about ONE thing, return a single-element list with the question itself. Max 3 "
    "items, same language as the question.\n"
    "\n"
    "Understand ANY language and ANY phrasing; ignore typos and glued tokens.\n"
    "\n"
    "Examples (Input -> Output):\n"
    'was sind neuronale Netze -> {"intent":"SPECIFIC","scope":{"unit":null,"intervals":[]},"subqueries":["was sind neuronale Netze"]}\n'
    'was schützt das Urheberrechtsgesetz und was das Markengesetz -> {"intent":"SPECIFIC","scope":{"unit":null,"intervals":[]},"subqueries":["was schützt das Urheberrechtsgesetz","was schützt das Markengesetz"]}\n'
    'Welche Stelle ist für die Steuerfestsetzung zuständig (Abgabenordnung) und welche Stellung hat der Rechtsanwalt (BRAO)? -> {"intent":"SPECIFIC","scope":{"unit":null,"intervals":[]},"subqueries":["Welche Stelle ist für die Steuerfestsetzung zuständig (Abgabenordnung)?","Welche Stellung hat der Rechtsanwalt (BRAO)?"]}\n'
    'fasse zusammen -> {"intent":"GENERIC","scope":{"unit":null,"intervals":[]}}\n'
    'gib mir einen Überblick -> {"intent":"GENERIC","scope":{"unit":null,"intervals":[]}}\n'
    'was sind die Hauptthemen -> {"intent":"GENERIC","scope":{"unit":null,"intervals":[]}}\n'
    'was sind neuronale Netze -> {"intent":"SPECIFIC","scope":{"unit":null,"intervals":[]}}\n'
    'wer hat das gesagt -> {"intent":"SPECIFIC","scope":{"unit":null,"intervals":[]}}\n'
    'unterschied zwischen X und Y -> {"intent":"SPECIFIC","scope":{"unit":null,"intervals":[]}}\n'
    'fasse Seite 12 zusammen -> {"intent":"GENERIC","scope":{"unit":"page","intervals":[[12,12]]}}\n'
    'fasse Seite 12 bis 14 zusammen -> {"intent":"GENERIC","scope":{"unit":"page","intervals":[[12,14]]}}\n'
    'ab Seite 10 -> {"intent":"GENERIC","scope":{"unit":"page","intervals":[[10,null]]}}\n'
    'Seite 5 und 10 -> {"intent":"SPECIFIC","scope":{"unit":"page","intervals":[[5,5],[10,10]]}}\n'
    'was wird bei Minute 10 erzählt -> {"intent":"SPECIFIC","scope":{"unit":"time","intervals":[[10,10]]}}\n'
    'fasse alles ab 10 min zusammen -> {"intent":"GENERIC","scope":{"unit":"time","intervals":[[10,null]]}}\n'
    'alles zwischen 12 und 13 -> {"intent":"SPECIFIC","scope":{"unit":"unknown","intervals":[[12,13]]}}\n'
)


# Nur angehaengt, wenn dem Vor-Call die letzte Runde beiliegt (kurze Eingabe, es
# gibt eine vorherige Runde, kein markierter Text). Ohne diesen Fall bekommt der
# Vor-Call Zeichen fuer Zeichen denselben Prompt wie vorher: seine Wegwahl ist
# fein abgestimmt und soll sich fuer den Normalfall nicht bewegen.
AIA_FOLLOWUP_BLOCK = (
    "\n"
    "FOLLOW-UP — the PREVIOUS TURN of this chat is attached ABOVE the new line. "
    "Add TWO more keys to the SAME JSON object:\n"
    '{"followup":"none"|"rewrite"|"reformat","standalone":"..."}\n'
    '- "none": the new line is a question that stands on its own — it names its own '
    'topic and does not depend on the previous turn. "standalone" = the new line unchanged.\n'
    '- "rewrite": the new line only makes sense TOGETHER with the previous turn '
    '("erkläre genauer", "warum ist das so?", "und was noch?", "das meinte ich nicht, ich '
    'meinte die Zwischenschritte"). "standalone" = ONE self-contained question that carries '
    'the TOPIC of the previous turn plus what the new line asks for.\n'
    '- "reformat": the new line asks to RESHAPE the previous ANSWER itself and wants no new '
    'content ("in 3 Stichpunkten", "kürzer", "als Tabelle", "fasse das zusammen"). '
    '"standalone" = a self-contained instruction naming the topic of the previous turn AND '
    'the requested shape.\n'
    "The standalone question MUST be written in the SAME language as the new line and must "
    "NEVER invent a topic that is in neither the previous turn nor the new line. If you are "
    'unsure, choose "none" — leaving the question alone is always the safe answer.\n'
    "DECIDE intent, scope AND subqueries ON THE STANDALONE QUESTION, not on the raw new line.\n"
    "\n"
    "Examples (previous turn -> new line -> output):\n"
    '"Was ist die Prüfungsleistung?" -> "erkläre genauer" -> {"intent":"SPECIFIC","scope":'
    '{"unit":null,"intervals":[]},"subqueries":["Erkläre die Prüfungsleistung genauer"],'
    '"followup":"rewrite","standalone":"Erkläre die Prüfungsleistung genauer"}\n'
    '"Was ist die Prüfungsleistung?" -> "in 3 kurzen Stichpunkten" -> {"intent":"GENERIC",'
    '"scope":{"unit":null,"intervals":[]},"followup":"reformat","standalone":"Fasse die '
    'Prüfungsleistung in 3 kurzen Stichpunkten zusammen"}\n'
    '"Was ist die Prüfungsleistung?" -> "was ist Quellenkritik" -> {"intent":"SPECIFIC",'
    '"scope":{"unit":null,"intervals":[]},"subqueries":["was ist Quellenkritik"],'
    '"followup":"none","standalone":"was ist Quellenkritik"}\n'
)


def aia_query_understanding_system(with_history: bool = False) -> str:
    """Systemprompt des Vor-Calls, mit dem Nachfrage-Block nur bei beiliegender Runde."""
    if not with_history:
        return AIA_QUERY_UNDERSTANDING_SYSTEM
    return AIA_QUERY_UNDERSTANDING_SYSTEM + AIA_FOLLOWUP_BLOCK


AIA_MINDMAP_PROMPT = (
    "You are an expert in knowledge structuring. Create a hierarchical mind map from the given text.\n\n"
    "Respond ONLY with a JSON object in exactly this format (4 levels). Topic and labels MUST be in {language}; the 'keyword' field MUST stay VERBATIM in the source-text language (see keyword rule below):\n"
    "{\n"
    '  "topic": "Central topic",\n'
    '  "children": [\n'
    "    {\n"
    '      "topic": "Main topic 1",\n'
    '      "source_label": "Filename.pdf",\n'
    '      "page_number": 3,\n'
    '      "keyword": "Machine Learning",\n'
    '      "children": [\n'
    "        {\n"
    '          "topic": "Subtopic 1a",\n'
    '          "source_label": "Filename.pdf",\n'
    '          "page_number": 5,\n'
    '          "keyword": "Neural Networks",\n'
    '          "children": [\n'
    '            { "topic": "Detail 1a-i", "source_label": "Filename.pdf", "page_number": 7, "keyword": "Backpropagation" },\n'
    '            { "topic": "Detail 1a-ii", "source_label": "Filename.pdf", "page_number": 8, "keyword": "Gradient Descent" }\n'
    "          ]\n"
    "        },\n"
    '        { "topic": "Subtopic 1b", "source_label": "Filename.pdf", "page_number": 10, "keyword": "Overfitting" }\n'
    "      ]\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Structure:\n"
    "- Level 1 (Root): umbrella topic that summarizes the entire content\n"
    "- Level 2: max 5-7 main topics\n"
    "- Level 3: max 3-5 subtopics per main topic\n"
    "- Level 4: max 2-3 details per subtopic (optional, only if needed)\n\n"
    "Rules:\n"
    "- Short, concise labels (max 6 words per node)\n"
    "- Only use information from the given text\n"
    "- When sources cover different topics: pick a connecting umbrella as the root, split main topics by subject area\n"
    "- For a single source: root = core topic of the document\n"
    "- Output language: write topic and node labels in {language}, regardless of the source-text language (translate the facts if needed). Field names stay English. EXCEPTION: the 'keyword' field MUST stay VERBATIM in the source-text language for PDF highlighting (see keyword rule).\n"
    "- IMPORTANT: every node (except root) MUST include source_label and page_number. "
    "source_label is the exact filename from the source citations [Filename, S. X] or [Filename, M:SS]. "
    "page_number is the page number (e.g. 3) or for audio/video sources the timestamp as a string (e.g. \"1:30\" or \"1:05:30\"), "
    "exactly as given in the source citations.\n"
    "- IMPORTANT: every node (except root) MUST include a keyword. "
    "keyword is a key term (1-3 words) that appears VERBATIM and UNCHANGED in the source text on the given page. "
    "DO NOT paraphrase. Copy the word directly from the source text. "
    "Example: if the source text contains 'intelligenten Assistenten', write keyword: 'intelligenten Assistenten', NOT 'KI-Assistenten'. "
    "The keyword is used for search/highlighting in the PDF and MUST be findable there exactly.\n"
    "- Respond ONLY with the JSON object, no other text."
)

AIA_LERNKARTEN_PROMPT = (
    "You are a language teacher for international students. "
    "Create flashcards for technical terms from the given text.\n\n"
    "IMPORTANT: All explanations MUST be easy to understand: simple words, short sentences, no nested clauses. "
    "When an adaptive block below states the learner's CEFR level, pitch the wording at that level instead.\n\n"
    "CRITICAL LANGUAGE RULE (overrides everything else): Write the explanatory fields "
    "(title, definition, word_parts_explained, example_sentence, word_class) ENTIRELY in {language}. "
    "Some examples further down are written in German for illustration only - IGNORE their language and always write in {language}. "
    "The 'begriff' (the technical term itself) stays VERBATIM in the source-text language, and the parts in "
    "'word_parts' / the part labels in 'word_parts_explained' / the forms in 'singular' and 'plural' / "
    "the verb forms in 'verb_present', 'verb_past' and 'verb_perfect' stay in that same language "
    "- they are the term being studied. "
    "So an English card about a German term reads e.g. begriff='Literaturrecherche', definition='Searching for books and articles to gather information.'\n\n"
    "Respond ONLY with a JSON object in exactly this format:\n"
    "{\n"
    '  "title": "Short title summarizing the topic (in {language})",\n'
    '  "cards": [\n'
    "    {\n"
    '      "begriff": "Fachbegriff",\n'
    '      "definition": "Einfache Definition (1-2 kurze Sätze)",\n'
    '      "word_parts": "Teil1 + Teil2 + Teil3",\n'
    '      "word_parts_explained": "Teil1 = einfache Erklärung | Teil2 = einfache Erklärung",\n'
    '      "example_sentence": "Ein einfacher Beispielsatz mit dem Begriff, wie man ihn im Studienalltag benutzt.",\n'
    '      "word_class": "part of speech, in {language}",\n'
    '      "singular": "singular form of the term with its article (fill for every noun)",\n'
    '      "plural": "plural form of the term with its article (fill unless the noun has no plural at all)",\n'
    '      "verb_present": "3rd person singular, present tense (verbs only)",\n'
    '      "verb_past": "3rd person singular, simple past (verbs only)",\n'
    '      "verb_perfect": "perfect form WITH its auxiliary (verbs only)",\n'
    '      "begriff_en": "English translation",\n'
    '      "source_label": "Filename.pdf",\n'
    '      "page_number": 5\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Create exactly {count} flashcards\n"
    "- Cards MUST cover ALL sources, not just one. Distribute evenly.\n"
    "- begriff: a central technical term from the text, in the source-text language\n"
    "- definition: a simple but ACCURATE definition in {language}. First name what the term IS "
    "(its category / genus), then add the one or two features that truly distinguish it. "
    "Write it so a student understands it immediately: simple words, short sentences, no jargon in the explanation. "
    "Do NOT add specifics the source does not support, do NOT narrow a general term down to one special case, "
    "and do NOT pad it with vague filler sentences that state nothing concrete. "
    "The definition must genuinely fit the term, not merely sound plausible.\n"
    "- word_parts: split into MEANINGFUL word parts (e.g. 'Studien + Abbruch + Quote'). "
    "ONLY for a term written as ONE word that is built from 2+ meaning-carrying parts. "
    "NOT for loanwords (Microcredentials, Employability), multi-word expressions (Hybride Lehre, machine learning), or simple words. Leave empty in those cases. "
    "Not every language builds such compounds - if the source language does not, leave the field empty rather than forcing a split.\n"
    "- word_parts ENDINGS ARE NOT PARTS: an ending (a suffix that cannot stand on its own as a word) is NEVER a word part. "
    "Look at the end of the term: if what comes off there is only an ending, the term is a single word that was merely extended, "
    "NOT a compound, so leave BOTH word_parts and word_parts_explained EMPTY and do not split that term anywhere else either. "
    "These German splits are WRONG and must never be produced: "
    "'Wirksamkeit' -> 'wirksam + Keit' is WRONG ('keit' is an ending, not a word), correct is word_parts = ''; "
    "'Wirklichkeit' -> 'wirklich + Keit' is WRONG, correct is ''; "
    "'Arbeitslosigkeit' -> 'Arbeit + los + igkeit' is WRONG, correct is '' (strip the ending and one single word 'arbeitslos' is left); "
    "'Bildung' -> 'Bild + ung' is WRONG, correct is ''. "
    "Real compounds are still split, because every part is a word on its own: "
    "'Brandverhütung' -> 'Brand + Verhütung', 'Studienabbruchquote' -> 'Studien + Abbruch + Quote'.\n"
    "- word_parts BASE FORM (applies to word_parts AND to the part labels in word_parts_explained): "
    "write each part in its DICTIONARY BASE FORM as it stands ALONE in its language, NOT as the raw slice cut out of the compound. "
    "Base form means: nouns in the singular nominative, verbs in the infinitive, adjectives uninflected. "
    "So turn a plural slice into its singular, drop any linking letters that only glue the compound together, "
    "and apply the language's own capitalisation rules to the standalone form. "
    "German examples: 'Passivsätze' -> 'Passiv + Satz' (NOT 'Passiv + Sätze', the plural becomes singular); "
    "'Hilfsverb' -> 'Hilfe + Verb' (NOT 'Hilfs + Verb', the linking -s is dropped); "
    "'Brandverhütung' -> 'Brand + Verhütung' (NOT 'Brand + verhütung', a noun part is capitalised). "
    "If a slice is still not a real standalone word after this, do NOT split there - merge it into the neighbouring part instead.\n"
    "- word_parts CAPITALISATION: capitalise ONLY the parts that are nouns. A part that is an adjective, a verb, "
    "an adverb, a preposition or a number stays lowercase, because that is how it is written standing alone. "
    "German examples: 'Primärliteratur' -> 'primär + Literatur' (NOT 'Primär + Literatur', 'primär' is an adjective); "
    "'Hochschule' -> 'hoch + Schule'; 'Lesekompetenz' -> 'lesen + Kompetenz'; "
    "'Studienabbruchquote' -> 'Studien + Abbruch + Quote' (all three are nouns, so all three are capitalised).\n"
    "- word_parts_explained: explain each part as simply as possible, the way you would explain it to a friend.\n"
    "- word_parts_explained ARTICLE: in the label before the '=', a part that is a NOUN carries its definite article, "
    "in the source language and matching that part's own gender. "
    "A part that is not a noun gets NO article and stays lowercase. "
    "An ending never appears here at all, so it never gets an article either "
    "('die Keit = eine Endung' is WRONG, the term simply has no word_parts). "
    "German examples: 'der Inhalt = das, was im Text steht | das Verzeichnis = eine Liste'; "
    "'primär = an erster Stelle | die Literatur = geschriebene Texte'. "
    "The 'word_parts' line itself stays WITHOUT articles ('Inhalt + Verzeichnis', 'primär + Literatur') "
    "- the articles appear only in word_parts_explained.\n"
    "- word_parts_explained WORD CLASS: the explanation MUST have the same word class as the part it explains. "
    "Explain a noun with a noun (or a noun phrase), a verb with a verb, an adjective with an adjective. "
    "German example: 'Verhütung = Schutz davor, dass etwas passiert' is correct, 'Verhütung = etwas verhindern' is WRONG (noun explained by a verb).\n"
    "- word_parts_explained MEANING IN CONTEXT: explain the meaning the part carries INSIDE this term and in the given source text, "
    "not a generic dictionary meaning that ignores the term. "
    "German example: in 'Rettungswege' write 'Wege = Strecken im Gebäude nach draußen', NOT 'Wege = Straßen oder Flure'. "
    "Stay simple and concrete: 'Studien = die Zeit an der Uni' helps, 'Studien = Plural von Studium' does not.\n"
    "- example_sentence: a SIMPLE example sentence showing how the term is used in everyday student life. "
    "Example for 'Studienabbruchquote': 'Die Studienabbruchquote ist hoch, viele Studenten hören auf, bevor sie fertig sind.' "
    "The sentence should help the student understand the term in context.\n"
    "- word_class: the part of speech of the begriff, written in {language} (e.g. Nomen / Verb / Adjektiv, or noun / verb / adjective). Always fill this.\n"
    "- word_class VERB MARKER: when the begriff is a VERB, append a bracket to the word class saying whether it is "
    "regular or irregular, and add the word for reflexive when the verb is reflexive. Write the bracket in {language}. "
    "German examples: 'sich treffen' -> 'Verb (unregelmäßig, reflexiv)'; 'lernen' -> 'Verb (regelmäßig)'; "
    "'sich beeilen' -> 'Verb (regelmäßig, reflexiv)'. Anything that is not a verb gets NO bracket.\n"
    "- verb_present, verb_past, verb_perfect: fill all three ONLY when the begriff is a verb, otherwise leave all three "
    "empty. Give the THIRD PERSON SINGULAR in each tense and keep the reflexive pronoun with the verb when it has one. "
    "verb_perfect MUST carry its auxiliary, because that is the part a learner cannot guess. "
    "German example 'sich treffen': verb_present='trifft sich', verb_past='traf sich', verb_perfect='hat sich getroffen'. "
    "German example 'lernen': verb_present='lernt', verb_past='lernte', verb_perfect='hat gelernt'. "
    "German example 'fahren': verb_present='fährt', verb_past='fuhr', verb_perfect='ist gefahren' (auxiliary 'ist', not 'hat').\n"
    "- verb forms CERTAINTY: if you are not fully certain of ONE of the forms, leave ALL THREE empty. "
    "A missing row costs the learner nothing, a wrong form teaches them something false.\n"
    "  GOOD: 'backen' -> verb_present='backt', verb_past='backte', verb_perfect='hat gebacken'\n"
    "  BAD: 'backen' -> verb_present='backt', verb_past='', verb_perfect='hat gebackt' (one form skipped, one invented)\n"
    "- A language that does not build these three tenses leaves all three empty rather than forcing a form.\n"
    "- singular and plural: for a term that is a single inflectable word (typically a noun), fill BOTH fields. "
    "Give the term's singular form and its plural form in the source language, each WITH its definite article if that language uses one "
    "(German: singular='der Fluchtweg', plural='die Fluchtwege'). "
    "A plural that exists but is rarely used is still a plural and MUST be given: "
    "'die Themenfindung' -> 'die Themenfindungen', 'die Zielsetzung' -> 'die Zielsetzungen'. "
    "Leave the plural empty ONLY when the noun has no plural at all (German 'das Wasser', 'der Hunger'), and still fill the singular in that case. "
    "Leave BOTH empty for multi-word terms, verbs, adjectives, and languages that do not mark number this way. "
    "Never fill the plural without the singular, and never invent a form that does not really exist.\n"
    "- begriff_en: English translation of the term\n"
    "- source_label and page_number: the primary source from the [SourceName, S. X] tags\n"
    "- Only use terms from the given text\n"
    "- Focus on central technical terms, NO comprehension questions\n"
    "- REMINDER: title, definition, word_parts_explained, example_sentence and word_class MUST be written in {language} "
    "(only begriff, word_parts, the part labels inside word_parts_explained, the singular/plural forms and the three "
    "verb forms keep the source language).\n"
    "- Respond ONLY with the JSON object, no other text."
)

# Der Tipp, den der Lernende an der Aufgabe aufklappt. Er entsteht im SELBEN Aufruf wie
# die Aufgabe. Vorher schickte der Tipp-Knopf eine Frage in den Chat: das kostete einen
# Modellaufruf pro Klick, warf den Lernenden aus der Aufgabe und lief bei jedem Anbieter
# ins Wartezimmer. Geteilt von Quiz und Karteikarten, damit die Regel nicht zweimal
# gepflegt werden muss.
#
# Das Verbot steht als Gegenbeispiel und nicht als Absichtserklaerung. Erfahrung aus dem
# Grammatik-Quiz: eine Regel, die das Modell an einem falschen Satz SIEHT, befolgt es,
# eine bloss formulierte oft nicht.
AIA_HINT_RULE = (
    "- tip: ONE short sentence that helps a learner who is stuck, WITHOUT giving the answer away. "
    "Point at where to look or what to think about: the situation, the comparison, or the example in "
    "the source that carries the idea. Never name the answer, never name one of the options, and never "
    "restate the answer in other words. Write it in {language} and address the learner directly and "
    "INFORMALLY: German 'du'/'dein' and the du-imperative ('Denk', 'Vergleich', 'Schau'), NEVER the "
    "formal 'Sie'/'Ihnen'/'Ihr'; in other languages the informal second person.\n"
    "  GOOD: \"Denk an das Beispiel der falsch kalibrierten Waage aus der Quelle.\"\n"
    "  BAD: \"Denken Sie an das Beispiel der falsch kalibrierten Waage.\" (formal address)\n"
    "  BAD: \"Erinnern Sie sich an die Aktivitaeten aus der Quelle.\" (formal address)\n"
    "  BAD: \"Die Antwort ist der systematische Fehler.\" (names the answer)\n"
    "  BAD: \"Lies den Text noch einmal.\" (helps nobody)\n"
)


# One-call question+answer cards: generate the Q AND the A in a single LLM call
# (no per-card RAG round-trip). Source links are attached post-hoc by pgvector
# attribution, so the prompt forbids citing — same contract as the chat RAG prompt.
AIA_KARTEIKARTEN_QA_PROMPT = (
    "You are an expert in learning materials. Generate {count} question-answer flashcards from the given documents. "
    "Each question AND its answer must be derivable using ONLY the documents (no general knowledge). "
    "Write everything in {language}, regardless of the source-text language. Translate source content into {language} if needed.\n\n"
    "Respond ONLY with a JSON object in exactly this format:\n"
    "{\n"
    '  "title": "Short title summarizing the overall topic (in {language})",\n'
    '  "cards": [{"question": "Question 1?", "answer": "Answer in 2-3 short sentences.", '
    '"tip": "One sentence that helps without giving the answer away."}]\n'
    "}\n\n"
    "Rules:\n"
    "- Exactly {count} cards\n"
    "- Comprehension/comparison/application questions (e.g. 'Warum...?', 'Erkläre...', 'Was ist der Unterschied...?')\n"
    "- NO pure definition questions - the goal is understanding and connections\n"
    "- Each question targets a different aspect of the documents\n"
    "- SINGLE-ASPECT questions only: ONE focused angle per question. NEVER combine multiple aspects "
    "with 'und', 'sowie', or list-enumerations like '(A, B, C, D)'.\n"
    "- Each answer is 2-3 short sentences of plain flowing text: NO markdown, NO bullet points, NO bold.\n"
    "- Do NOT cite sources, page numbers, or document numbers in the answer - the clickable source links are attached automatically afterwards.\n"
    "- Do NOT use personal names; write 'laut Quelle' (German) or 'according to the source' (English), matching the output language.\n"
    + AIA_HINT_RULE +
    "- Respond ONLY with the JSON object, no other text."
)


# Aus fertigen Glossarbegriffen echte Frage-Antwort-Karten. Getrennt von
# AIA_KARTEIKARTEN_QA_PROMPT, weil der dort verbotene Definitionsbezug hier genau die
# Aufgabe ist: die Definition steht schon fest, gesucht ist die Frage dazu.
AIA_KARTEIKARTEN_GLOSSAR_PROMPT = (
    "You turn glossary entries into question-answer flashcards. Each entry already has a term "
    "and a definition; your job is to write the QUESTION that the definition answers.\n\n"
    "Write everything in {language}.\n\n"
    "Respond ONLY with a JSON object in exactly this format:\n"
    "{\n"
    '  "cards": [{"term": "the term, VERBATIM as given", "question": "Question?", '
    '"answer": "Answer in 1-3 short sentences."}]\n'
    "}\n\n"
    "Rules:\n"
    "- EXACTLY one card per given entry, in the same order, and no others\n"
    "- 'term' is copied VERBATIM from the input; it is how the card is matched back\n"
    "- The question must be answerable by the given definition and by nothing else. Do NOT add "
    "facts, examples or specifics that are not in the definition\n"
    "- VARY the phrasing. Do not start every question the same way; ask what something means, "
    "what it is for, what distinguishes it, when it is used\n"
    "- The question names the term. A card whose question could fit any term is useless\n"
    "- The answer restates the given definition in clear, simple language: plain flowing text, "
    "NO markdown, NO bullet points, NO bold\n"
    "- Do NOT cite sources or page numbers; the clickable source links are attached afterwards\n"
    "- Respond ONLY with the JSON object, no other text."
)


AIA_DATENTABELLE_PROMPT = (
    "You are an expert in data extraction and structuring. "
    "Analyze the given text and create a structured data table. "
    "Write title, column headers, and cell values in {language}, regardless of the source-text language (translate the content if needed). EXCEPTION: the 'highlight' field MUST stay VERBATIM in the source-text language for PDF highlighting (see highlight rule).\n\n"
    "Respond ONLY with a JSON object in exactly this format:\n"
    "{\n"
    '  "title": "Descriptive table title (in {language})",\n'
    '  "columns": ["Column1", "Column2", "Column3"],\n'
    '  "rows": [\n'
    '    { "cells": ["Value1", "Value2", "Value3"], "sources": [{"source_label": "Filename.pdf", "page": 3, "highlight": "TechTerm"}] },\n'
    '    { "cells": ["Value4", "Value5", "Value6"], "sources": [{"source_label": "Filename.pdf", "page": 5, "highlight": "Keyword"}, {"source_label": "Other.pdf", "page": 2, "highlight": "Term"}] }\n'
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Choose meaningful columns that best structure the content\n"
    "- Minimum 3, maximum 8 columns\n"
    "- Each row contains a 'cells' array (same length as 'columns') and a 'sources' array\n"
    "- IMPORTANT: every entry in 'sources' MUST contain 'source_label' (exact filename from the source citations), 'page', and 'highlight'. "
    "'page' is the page number for PDFs (from [Filename, S. X]) or the timestamp as a string for media files (from [Filename, M:SS] or [Filename, H:MM:SS]). "
    "'highlight' is a key term (1-3 words) that appears VERBATIM and UNCHANGED in the given source text. "
    "DO NOT paraphrase. Copy the word directly from the source text. "
    "Example: if the source text contains 'intelligenten Assistenten', write highlight: 'intelligenten Assistenten', NOT 'KI-Assistenten'. "
    "The highlight is used for search/highlighting in the PDF and MUST be findable there exactly.\n"
    "- Extract as many rows as the text supports (no invented data)\n"
    "- The title should briefly describe the table content\n"
    "- Keep cell values concise but informative\n"
    "- Only use information from the given text\n"
    "- Do NOT add a column for sources/citations/filenames in 'columns'. Sources are referenced separately via the 'sources' array per row.\n"
    "- Respond ONLY with the JSON object, no other text."
)


AIA_SCHEDULE_CLASSIFY_PROMPT = (
    "You classify date candidates extracted by regex from course documents.\n"
    "For EACH candidate (identified by `id`) you must decide whether it represents "
    "a real scheduled event/deadline the student should see on their schedule - "
    "or whether it is document metadata (slide date, author, footer, version) and "
    "must be dropped.\n\n"
    "Respond ONLY with a JSON object of the form:\n"
    '{ "results": [ { "id": int, "keep": bool, "is_footer": bool, "is_header": bool, "is_historical": bool, '
    '"type": "deadline" | "termin" | null, "title": "..." | null, '
    '"description": "..." | null, "due_time": "HH:MM" | null, "is_optional": bool } ] }\n\n'
    "Keep ALL fields as concise as possible. No `reason` field - just the decision fields.\n\n"
    "Per candidate input you receive `date_raw`, `date_iso`, and `context` "
    "(±250 chars around the date from the source text).\n\n"
    "DECISION RULES:\n"
    "1. keep=true only when the context clearly describes an ORGANIZATIONAL event "
    "the student must act on or attend (deadline, exam, meeting, office hour, "
    "web conference, submission, lecture session). A scheduling verb/preposition "
    "is required ('am X findet', 'bis X abgeben', 'deadline on X', 'Abgabe:', "
    "'Klausur am', 'Meeting on', 'submission by').\n"
    "2. keep=false when the date is page chrome, not body content. Set is_footer=true for "
    "footer/document metadata: near author names, 'M.Sc.', 'Prof.', emails, 'Mentor', "
    "'Tutor', 'Kontakt', 'Folie', 'Seite', 'Slide', version, or a page number, without any "
    "scheduling verb. Set is_header=true for a running header or cover-sheet date that "
    "repeats at the top of pages/slides (the same lecture/document date printed on every "
    "page, a title-block date, 'Stand: <date>'), again without any scheduling verb. Both "
    "is_footer and is_header are dropped.\n"
    "3. keep=false / is_historical=true when the date is merely a reference to the "
    "past or a historical fact ('letztes Jahr am 3. Juli fand die Prüfung statt', "
    "'im Wintersemester 2024/25 wurde X präsentiert', 'seit 2019 existiert'). "
    "The student does not act on these.\n"
    "4. keep=false for relative time expressions being normalized ('noch 20 Tage', "
    "'in 3 weeks'), and for recurring-only phrases like 'jeden Dienstag' without a "
    "concrete single date.\n"
    "5. For year-full candidates: keep=false if the year in the ISO date does not "
    "appear as a 4-digit number in the surrounding context (anti-hallucination).\n"
    "6c. `month_only=true` means the source names only a month, no day ('im Juli 2026', "
    "'Temmuz 2026'). date_iso then carries the 1st of that month as a sorting point, and "
    "the UI shows only the month. Judge it like any other event and do NOT drop it for "
    "missing a day. In the title, do not invent a day either.\n"
    "6b. `documented_with_year_elsewhere=true` on a year-less candidate means another "
    "source of the SAME course carries this exact day WITH a year (e.g. the syllabus "
    "PDF says '03.07.2026' and a lecture recording says 'der 3. Juli'). That is the "
    "SAME event mentioned again, NOT a historical reference: keep=true, is_historical="
    "false, even when the day already passed, and give it the event title. Spoken "
    "recordings are the main case - they are how a source other than the PDF ends up "
    "on the entry. Only set keep=false when the context clearly speaks about a "
    "PREVIOUS run of the course ('letztes Semester', 'im Jahr davor').\n"
    "6. For year-less candidates (year_missing=true): the system will ALWAYS "
    "resolve the year to the CURRENT calendar year - never to a past or future "
    "year. Decide from context: is this describing an organizational event for "
    "the current term (keep=true), or is it a historical/referential mention "
    "(keep=false / is_historical=true)? If the month/day would fall in the past "
    "of the current year AND the context does not clearly frame it as an event "
    "of this term, classify it as historical.\n"
    "7. For TBD candidates (date_tbd=true, e.g. 'nach Vereinbarung' / 'nach Absprache' / "
    "'TBD' / 'fecha a convenir' / any other language): keep=true if the context "
    "describes a real scheduled event whose date "
    "is simply not yet fixed (e.g. 'Präsentationstermine nach Vereinbarung', "
    "'Sprechstunde nach Absprache'). These will be stored without a date and "
    "shown as a 'Nach Vereinbarung' block in the UI. keep=false if the phrase "
    "just describes a policy without an actual event.\n"
    "8. 'Opening' / 'Freischaltung' dates are NOT deadlines: keep=false for candidates "
    "whose context frames the date as the START or AVAILABILITY of a submission window, "
    "NOT the submission deadline itself. Signals: 'geöffnet ab', 'freigeschaltet am', "
    "'Einreichung möglich ab', 'opens on', 'available from', 'starts'. Example: "
    "'Geöffnet ab 13.04.2026, 19:00 - Abgabe bis 20.04.2026, 18:00' → keep=true ONLY "
    "for the 20.04.2026 deadline, keep=false for the 13.04.2026 opening. When in doubt "
    "(context describes BOTH an opening and a later deadline on the same event), keep "
    "only the final/latest deadline and drop the opening.\n"
    "7. 'Ab <date>' (starting on a date) is ONE entry, not recurring - keep=true.\n\n"
    "FIELDS (when keep=true):\n"
    "- type='deadline' for submissions/hand-ins/filings tied to a due date "
    "(Abgabe, Einreichung, Frist, submission).\n"
    "- type='termin' for events that take place at a date (exam, meeting, web "
    "conference, lecture, guest talk, Klausur, Vorlesung, Webkonferenz).\n"
    "- title: short, in the SOURCE language. For submissions use 'Abgabe <Code>: "
    "<Topic>' (German sources) or 'Submission <Code>: <Topic>' (English). For events "
    "use '<Kind>: <Topic>' where <Kind> is a concrete noun like 'Webkonferenz', "
    "'Vorlesung', 'Sprechstunde', 'Klausur', 'Online-Präsenz', 'Meeting'. Mark "
    "optional entries in parentheses at the end: '(optional)' or '(freiwillig)'.\n"
    "- title MUST be a COMPLETE, semantically self-contained phrase describing the "
    "event. Never produce truncated fragments like 'Finale: kleine', 'Abgabe: nun', "
    "'Termin: ein'. NEVER produce single-word adjective/qualifier titles like "
    "'Finale', 'Endgültig', 'Abschluss' alone - these describe a property, not an "
    "event. The title must always include the EVENT NOUN ('Abgabe Hausarbeit', "
    "'Endklausur', 'Abschlusspräsentation'). If the surrounding context is too "
    "noisy or fragmentary (typical for spoken video transcripts where the date is "
    "only referenced in passing), reuse the canonical event noun the speaker is "
    "obviously alluding to rather than splicing random surface words. If even that "
    "is impossible, set keep=false.\n"
    "- VIDEO TRANSCRIPT CONTEXT: spoken language is informal and disfluent. Treat "
    "fillers ('also', 'ja', 'so'), hedges ('vielleicht', 'eventuell'), and "
    "qualifiers ('kleine', 'finale', 'eigentlich') as NOISE - never lift them into "
    "the title. Identify the underlying noun phrase the speaker refers to (e.g. 'die "
    "finale, kleine Korrektur der Hausarbeit gibt's bis zum 03.07.' → title "
    "'Abgabe Hausarbeit', NOT 'Finale: kleine').\n"
    "- NEVER prefix titles with generic words like 'Termin:', 'Event:', 'Event -', "
    "'Eintrag:' - the entry's type already conveys this. Write 'Webkonferenz: X' "
    "not 'Termin: Webkonferenz (X)'. Be consistent across all entries.\n"
    "- CROSS-CANDIDATE CONSISTENCY: If multiple candidates describe the SAME event on "
    "the SAME date (e.g. three mentions of the same office-hour opening, or the same "
    "submission deadline referenced from different PDFs / video transcripts), give "
    "them the EXACT same title string - downstream deduplication relies on identical "
    "titles for merging.\n"
    "- description: concise extra details from the context, or null. The due_time is "
    "rendered separately by the UI, so NEVER repeat the start time here in any form "
    "(no 'um 23:59 Uhr', no '2359 Uhr', no 'um 10:00'). If the only extra info would "
    "be the start time itself, return null. For time RANGES (e.g. context shows '10 "
    "bis 13:15 Uhr' or '10:00-13:15'), set due_time to the START ('10:00') and put "
    "ONLY the end into description as 'bis HH:MM Uhr' - never include the start.\n"
    "- due_time: 'HH:MM' if the time is in context. For TABLE/SERIES layouts "
    "(multiple dated rows like 'Webkonferenzen' or 'Vorlesungen'), a time listed "
    "ONCE in the header or for the first row applies to ALL rows of the same "
    "kind unless another time is given explicitly. Inherit it so every event in "
    "the series gets the same due_time. Leave null only when no time is visible "
    "anywhere in the surrounding context.\n"
    "- is_optional: true only if context explicitly says 'freiwillig', 'optional', "
    "'nach Wahl', 'voluntary'.\n\n"
    "STRICT JSON RULES:\n"
    "- Plain double quotes only; no markdown, no German „..\" quotes, no emphasis.\n"
    "- results array length MUST equal the input candidates length; use same ids.\n"
    "- Do not invent dates; operate only on the given candidates.\n"
    "- Output compact JSON (no unnecessary whitespace or indentation).\n"
)


AIA_SCHEDULE_TBD_DISCOVER_PROMPT = (
    "You read raw text blocks from course documents and do TWO jobs on them.\n\n"
    "JOB 2 (key \"dates\"): find the dates the system cannot read on its own.\n"
    "It ALREADY reads these four, skip them: 'DD.MM.YYYY' (03.07.2026), 'YYYY-MM-DD', "
    "'MM.YYYY' (06.2026), and month names written out in German or English ('3. Juli "
    "2026', 'July 3, 2026').\n"
    "REPORT everything else that is a date, above all:\n"
    "- month names in ANY OTHER language: '3 Temmuz 2026' (Turkish), '3 juillet 2026' "
    "(French), '3 de julio de 2026' (Spanish), 'Eylul 2026'.\n"
    "- numeric dates with a TWO-DIGIT year: '3.6.26', '03.06.26', '03/06/26'. Expand the "
    "year to four digits ('26' in a course document of 2026 means 2026).\n"
    "- numeric dates with other separators: '03/06/2026', '3-6-2026'.\n"
    "BUT: a string of numbers is only a date when the sentence around it means a date. "
    "An outline number ('3.6.26 Zusammenfassung der Ergebnisse'), a section, a version, "
    "a page or a decimal number is NOT a date, no matter how much it looks like one. "
    "When the context does not clearly say 'this is when something happens', leave it "
    "out. A missed date is better than an invented one.\n"
    "Report EVERY such date of a block, not just the first one. Two dates in one "
    "sentence are two entries in `dates`.\n"
    "For each one return:\n"
    "- `phrase`: the date CHARACTER FOR CHARACTER as it stands in the block.\n"
    "- `date`: the same date in digits, in EXACTLY one of these three shapes:\n"
    "    'YYYY-MM-DD' when day, month and year are known ('3 Temmuz 2026').\n"
    "    'YYYY-MM'    when only month and year are known ('Temmuz 2026', 'im Juli 2026').\n"
    "    'MM-DD'      when only day and month are known, no year ('3 Temmuz', '3. Juli').\n"
    "Never invent a part that is not in the text: no day when only the month is named, "
    "no year when no year is named. Vague spans like 'Ende Mai', 'Anfang Juli', 'im "
    "Sommersemester', 'in drei Wochen' are NOT dates, leave them out. A weekday alone "
    "('jeden Dienstag') is not a date either. At most 6 dates per block, the clearest "
    "ones.\n\n"
    "JOB 1 (key \"results\"): find the places where a real "
    "event, appointment or deadline is announced WITHOUT a fixed date, because the date "
    "is still to be arranged or will be announced later.\n\n"
    "Typical wordings (examples only, NOT a checklist): 'Präsentationstermine nach "
    "Vereinbarung', 'Sprechstunde nach Absprache', 'exam date to be announced', 'fecha a "
    "convenir', 'tarih daha sonra duyurulacak', 'date à convenir', 'TBA'.\n\n"
    "THE TEXT CAN BE IN ANY LANGUAGE. Never rely on a fixed list of words. Decide from "
    "meaning: is an event named, and is its date left open on purpose?\n\n"
    "Respond ONLY with a JSON object of the form:\n"
    '{ "results": [ { "id": int, "phrase": "..." } ], '
    '"dates": [ { "id": int, "phrase": "...", "date": "..." } ] }\n\n'
    "Both arrays are usually SHORTER than the input and either may be empty. A block "
    "can appear in both, in one, or in neither.\n\n"
    "RULES (they apply to the `phrase` of BOTH jobs):\n"
    "1. `phrase` MUST be copied CHARACTER FOR CHARACTER from that block. Do not "
    "translate it, do not fix spelling, do not shorten words. A phrase that is not "
    "literally in the block is discarded by the system.\n"
    "2. Keep the phrase short: in `results` the event plus the open-date wording, at "
    "most 80 characters, starting at the event name when it stands right next to the "
    "wording. In `dates` the phrase is ONLY the date itself.\n"
    "3. At most ONE entry in `results` per block: the clearest place. Blocks with "
    "nothing to report are simply left out.\n"
    "4. Do NOT report a place in `results` that already carries a date of ANY precision, "
    "including a bare month or a concrete weekday+time rule ('every Tuesday 10:00'). "
    "'Sunum: Eylul 2026 icinde yapilacak, gun henuz belli degil' HAS its date (the "
    "month), it belongs in `dates` only, never in `results`. Only a place with no date "
    "at all is an open one.\n"
    "5. Do NOT report general policy sentences without a concrete event ('deadlines are "
    "communicated by mail', 'rules can change'), and do NOT report an empty column or a "
    "dash in a table just because a date is missing.\n"
    "6. A missing date is NOT enough. The text itself must SAY that the date is still "
    "open ('will be arranged', 'to be announced', 'agreed individually'). An event "
    "mentioned without any date is NOT a result.\n"
    "7. Do NOT report a pointer to where the dates already are ('you can look up when "
    "the peer reviews take place in the course plan', 'see the syllabus', 'check "
    "Moodle'), and do NOT report a question or a subordinate clause about WHEN something "
    "happens. Those refer to dates that exist elsewhere, they do not announce an open "
    "one. This matters most in spoken transcripts, where such sentences are frequent.\n\n"
    "STRICT JSON RULES:\n"
    "- Plain double quotes only; no markdown, no German „..\" quotes.\n"
    "- Use the block ids from the input; never invent ids.\n"
    "- Output compact JSON (no unnecessary whitespace or indentation).\n"
)


AIA_SCHEDULE_HARMONIZE_PROMPT = (
    "You receive a list of events that all occur on the SAME date. They come from "
    "different sources (PDFs, video transcripts) and may be worded differently even "
    "though they describe the SAME real-world event.\n\n"
    "Each item has a `role` field:\n"
    "- role='existing' → already in the database, title is FIXED, do NOT invent a new one.\n"
    "- role='candidate' → newly extracted, title can be rewritten.\n"
    "- Item ids are strings: 'c<N>' for candidates, 'e<N>' for existing entries.\n\n"
    "Your job: group items that refer to the SAME event. Pick ONE canonical title per group.\n"
    "- If a group contains an 'existing' item, canonical_title MUST equal that existing's title.\n"
    "- If a group has only 'candidate' items, pick the clearest wording from them.\n"
    "- Distinct events on the same date stay in SEPARATE groups (singleton group is fine).\n\n"
    "Examples of SAME event, different wording:\n"
    "- 'Abgabe: schriftliche Ausarbeitung' and 'Abgabe: Prüfungsleistung' - same final hand-in.\n"
    "- 'Abgabe Hausarbeit' and 'Abgabe: schriftliche Ausarbeitung und Präsentation' - "
    "  same final hand-in (Hausarbeit = schriftliche Ausarbeitung).\n"
    "- 'Abgabe Hausarbeit' and 'Finale' / 'Endabgabe' / 'Abschluss' - vague "
    "  single-word titles from video transcripts almost always refer to the "
    "  formal deadline captured in PDFs. Merge them into the specific title.\n"
    "- 'Offene Sprechstunde: Beginn' and 'Offene Sprechstunde (ab 22.04.)' - same start.\n"
    "- 'Webkonferenz' and 'Online-Meeting' if context matches.\n\n"
    "BIAS TOWARD MERGING when same date + one vague title + one specific event "
    "title. Vague titles from video transcripts ('Finale', 'Endrunde', 'Abschluss', "
    "single nouns/adjectives) usually echo the formal event documented elsewhere; "
    "merge into the specific title unless context clearly contradicts it.\n\n"
    "Examples of DIFFERENT events on the same date (keep separate):\n"
    "- 'Abgabe: Hausarbeit' vs 'Klausur' - clearly different.\n"
    "- 'Vorlesung Modul A' vs 'Vorlesung Modul B' - distinct sessions.\n\n"
    "Canonical title rules (for candidate-only groups):\n"
    "- Clearest, most specific wording from the group.\n"
    "- Keep source language (German input → German title).\n"
    "- Preserve '(freiwillig)' / '(optional)' if any group member had it.\n"
    "- For deadlines, prefer 'Abgabe: <Topic>' format.\n\n"
    "Respond ONLY with a JSON object:\n"
    '{ "groups": [ { "ids": ["c0", "e42", ...], "canonical_title": "..." }, ... ] }\n\n'
    "Every input id must appear in exactly ONE group. Plain double quotes only, no markdown."
)


AIA_POPUP_ACTIONS: list[dict[str, str | int]] = [
    {
        "key": "translate",
        "label_de": "Übersetzen",
        "label_en": "Translate",
        "icon": "Translate",
        # Die Zielsprache ist eine Einstellung der lesenden Person, nicht mehr
        # ein festes Hin und Her zwischen Deutsch und Englisch. Eingesetzt wird
        # der ENGLISCHE Sprachname (Spanish, Turkish). Das erspart die Beugung
        # im deutschen Prompt ("ins Spanische" gegen "ins Türkische") und das
        # Modell versteht beides gleich gut.
        "prompt_de": (
            "Übersetze die markierte Passage. "
            "Zielsprache: {language}. "
            "Ist die Passage bereits in dieser Sprache, gib sie unverändert zurück. "
            "Nutze den umgebenden Dokumentkontext, um Mehrdeutigkeiten, Fachbegriffe "
            "und Wörter mit mehreren möglichen Bedeutungen korrekt aufzulösen. "
            "Gib NUR die Übersetzung aus — keine Erklärungen, keine Anmerkungen, "
            "kein Originaltext, keine Anführungszeichen. "
            "Behalte Register, Ton und Stil des Originals:"
        ),
        "prompt_en": (
            "Translate the marked passage. "
            "Target language: {language}. "
            "If the passage is already in that language, return it unchanged. "
            "Use the surrounding document context to disambiguate ambiguous terms, "
            "domain-specific vocabulary, and words with multiple possible meanings. "
            "Output ONLY the translation — no explanations, no notes, no original text, "
            "no quotation marks. Preserve register, tone, and style of the original:"
        ),
        "min_words": 1,
    },
    {
        "key": "simplify",
        # B1 is the DEFAULT register, not a hard cap (same "B1 by default, adaptive
        # block overrides" pattern as the glossary prompts). When the learner has the
        # Fachsprachentrainer on, chat.py appends the adaptive suffix to this same user
        # message; the prompt below and the suffix's "OVERRIDES ... terminology rules
        # above" clause both re-pitch the explanation to the learner's own CEFR level
        # (down for A1/A2, up for B2-C2). Without the trainer, B1 stands.
        "label_de": "Erklären",
        "label_en": "Explain",
        "icon": "Lightbulb",
        "prompt_de": (
            "Erkläre diese Passage so, dass jemand ohne Vorwissen sie versteht. "
            "Erkläre standardmäßig auf Niveau B1. Wenn am Ende ein adaptiver Block das "
            "CEFR-Niveau der lernenden Person nennt, erkläre stattdessen auf DIESEM Niveau "
            "statt B1 und richte danach aus, wie stark du vereinfachst. "
            "Ersetze Fachbegriffe durch alltagssprachliche Umschreibungen oder, wo das nicht geht, "
            "definiere den Begriff in einem Halbsatz. "
            "Nutze kurze Sätze und eine konkrete Alltagsanalogie, falls hilfreich. "
            "Fließtext, keine Stichpunkte. "
            "Antworte in der Sprache des Originaltexts:"
        ),
        "prompt_en": (
            "Explain this passage so someone without prior knowledge understands it. "
            "Explain at B1 level BY DEFAULT. If an adaptive block at the end names the "
            "learner's CEFR level, explain at THAT level instead of B1 and let it decide "
            "how much you simplify. "
            "Replace jargon with everyday wording or, where that isn't possible, "
            "define the term in a half-sentence. "
            "Use short sentences and a concrete everyday analogy if it helps. "
            "Flowing text, no bullet points. "
            "Respond in the source-text language:"
        ),
        "min_words": 3,
    },
]
