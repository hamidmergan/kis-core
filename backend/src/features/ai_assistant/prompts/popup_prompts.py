"""Prompts der Auswahlleiste und des Notiz-Titels."""



# -- Auswahlleiste: Systemprompts ---------------------------------------------

# Alle Aktionen ausser "Erklaeren", das Modell sieht nur die Markierung.
AIA_SYSTEM_DIRECT = (
    "You are a helpful assistant. Execute the task precisely. "
    "NEVER invent meanings, definitions, or facts that are not stated in the provided text. "
    "Respond in the user's language."
)

# Nur "Erklaeren", Markierung plus Umgebung aus dem Dokument.
AIA_SYSTEM_DIRECT_WITH_CONTEXT = (
    "You are a helpful assistant. Execute the task precisely. "
    "Use ONLY information from the provided text. "
    "NEVER invent meanings, definitions, or facts that are not explicitly stated in the text. "
    "If something is unclear, say it is not explained in the text. "
    "Respond in the user's language."
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


AIA_POPUP_ACTIONS: list[dict[str, str | int]] = [
    {
        "key": "translate",
        "label_de": "Übersetzen",
        "label_en": "Translate",
        "icon": "Translate",
        # Zielsprache ist eine Einstellung des Lesers. Eingesetzt wird der ENGLISCHE
        # Sprachname (Spanish), das erspart die deutsche Beugung ("ins Türkische").
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
