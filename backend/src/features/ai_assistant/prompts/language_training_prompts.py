"""Prompts des Sprachtrainers: Lernkarten, Karteikarten, Glossar."""


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

# Der Tipp entsteht im SELBEN Aufruf wie die Aufgabe. Vorher kostete der Tipp-Knopf einen
# Modellaufruf pro Klick und warf den Lernenden aus der Aufgabe. Geteilt von Quiz und
# Karteikarten.
#
# Das Verbot steht als Gegenbeispiel: eine Regel, die das Modell an einem falschen Satz
# SIEHT, befolgt es, eine bloss formulierte oft nicht.
AIA_HINT_RULE = (
    "- tip: ONE short sentence that helps a learner who is stuck, WITHOUT giving the answer away. "
    "Point at the thought that leads there: the situation, the comparison, or the example in "
    "the source that carries the idea. Never name the answer, never name one of the options, and never "
    "restate the answer in other words. Write it in {language} and address the learner directly and "
    "INFORMALLY: German 'du'/'dein' and the du-imperative ('Denk', 'Vergleich', 'Schau'), NEVER the "
    "formal 'Sie'/'Ihnen'/'Ihr'; in other languages the informal second person.\n"
    "  NEVER point at a place in the material: no page number, no timestamp, no filename, no section "
    "number, and never an ordinal such as 'die erste Quelle' or 'das zweite Dokument'. The learner "
    "never sees that numbering, and a clickable source link already sits right under the tip.\n"
    "  If the tip names a term, write it EXACTLY as the source text writes it, never a paraphrase of "
    "it. A learner who searches for a word that is not in the material finds nothing.\n"
    "  GOOD: \"Denk an das Beispiel der falsch kalibrierten Waage aus der Quelle.\"\n"
    "  BAD: \"Denken Sie an das Beispiel der falsch kalibrierten Waage.\" (formal address)\n"
    "  BAD: \"Erinnern Sie sich an die Aktivitaeten aus der Quelle.\" (formal address)\n"
    "  BAD: \"Die Antwort ist der systematische Fehler.\" (names the answer)\n"
    "  BAD: \"Lies den Text noch einmal.\" (helps nobody)\n"
    "  BAD: \"Schau in S. 2 der ersten Quelle nach.\" (points at a place, and the numbering means "
    "nothing to the learner)\n"
    "  BAD: \"Achte auf das wichtigste Hilfsmittel.\" (invents a word the source never uses)\n"
)


# Q AND A in a single call, no per-card RAG round-trip. Source links are attached
# post-hoc, so the prompt forbids citing.
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
