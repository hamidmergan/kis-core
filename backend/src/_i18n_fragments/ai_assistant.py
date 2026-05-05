"""i18n message fragments for AI Assistant routes."""

MESSAGES: dict[str, dict[str, str]] = {
    # Workspace / module
    "ai.workspace.translationModeInvalid": {
        "de": "Ungültiger Übersetzungs-Modus",
        "en": "Invalid translation mode",
    },
    "ai.workspace.transcriptDefaultLangInvalid": {
        "de": "Ungültige Standard-Transkript-Sprache",
        "en": "Invalid default transcript language",
    },
    "ai.workspace.invalidEnrollCode": {
        "de": "Ungültiger oder abgelaufener Einschreibecode",
        "en": "Invalid or expired enrollment code",
    },
    "ai.workspace.maxAccessLinks": {
        "de": "Maximal {max} Einschreibelinks pro Modul erlaubt. Bitte lösche zuerst einen alten Link.",
        "en": "Maximum {max} enrollment links per workspace allowed. Please delete an old link first.",
    },
    # Sources
    "ai.source.maxPerWorkspace": {
        "de": "Maximal {max} Sources pro Workspace erlaubt. Bitte lösche nicht mehr benötigte Sources.",
        "en": "Maximum {max} sources per workspace allowed. Please delete sources you no longer need.",
    },
    "ai.source.maxAllowed": {
        "de": "Maximal {max} Sources erlaubt",
        "en": "Maximum {max} sources allowed",
    },
    "ai.source.noValidSelected": {
        "de": "Keine gültigen Sources ausgewählt",
        "en": "No valid sources selected",
    },
    "ai.source.noneSelected": {
        "de": "Keine Sources ausgewählt",
        "en": "No sources selected",
    },
    "ai.source.notSelected": {
        "de": "Keine Source angegeben",
        "en": "No source specified",
    },
    "ai.source.allowedExtensions": {
        "de": "Nur {extensions} erlaubt",
        "en": "Only {extensions} allowed",
    },
    "ai.source.fileTooLargeMb": {
        "de": "Datei zu groß (max {max} MB)",
        "en": "File too large (max {max} MB)",
    },
    "ai.source.tooManyPages": {
        "de": "Dokument hat {pages} Seiten - max. {max} Seiten erlaubt. Bitte teile das Dokument in kleinere Abschnitte auf.",
        "en": "Document has {pages} pages - max. {max} pages allowed. Please split the document into smaller sections.",
    },
    "ai.source.retryFailedOnly": {
        "de": "Nur fehlgeschlagene Sources können neu indexiert werden",
        "en": "Only failed sources can be re-indexed",
    },
    "ai.source.pdfOnly": {
        "de": "Nur für PDF-Dateien verfügbar",
        "en": "Only available for PDF files",
    },
    "ai.source.pdfConversionFailed": {
        "de": "Konvertierung nach PDF fehlgeschlagen",
        "en": "Conversion to PDF failed",
    },
    # Chat / RAG
    "ai.chat.noIndexedSources": {
        "de": "Keine indizierten Sources vorhanden",
        "en": "No indexed sources available",
    },
    # Glossary
    "ai.glossary.extractionFailed": {
        "de": "Extraktion fehlgeschlagen",
        "en": "Extraction failed",
    },
    # Notes
    "ai.notes.maxPerWorkspace": {
        "de": "Maximal {max} Notizen pro Workspace erlaubt. Bitte lösche nicht mehr benötigte Notizen.",
        "en": "Maximum {max} notes per workspace allowed. Please delete notes you no longer need.",
    },
    # Schedule
    "ai.schedule.invalidDate": {
        "de": "Ungültiges Datum: {value}",
        "en": "Invalid date: {value}",
    },
    "ai.schedule.invalidTime": {
        "de": "Ungültige Uhrzeit: {value}",
        "en": "Invalid time: {value}",
    },
    "ai.schedule.limitRange": {
        "de": "limit muss zwischen 1 und 500 liegen",
        "en": "limit must be between 1 and 500",
    },
    "ai.schedule.offsetRange": {
        "de": "offset muss >= 0 sein",
        "en": "offset must be >= 0",
    },
    "ai.schedule.jobNotFound": {
        "de": "Job nicht gefunden",
        "en": "Job not found",
    },
    # Studio (mindmap, data_table)
    "ai.dataTable.notFound": {
        "de": "DataTable nicht gefunden",
        "en": "Data table not found",
    },
    # Transcripts
    "ai.transcript.translationDisabled": {
        "de": "EN-Übersetzung ist für diesen Workspace deaktiviert",
        "en": "EN translation is disabled for this workspace",
    },
    "ai.transcript.invalidProvider": {
        "de": "Ungültiger Provider",
        "en": "Invalid provider",
    },
    "ai.transcript.sourceMissing": {
        "de": "Kein Quell-Transkript gefunden. Neu-Übersetzung nicht möglich.",
        "en": "No source transcript found. Re-translation not possible.",
    },
    "ai.transcript.invalidLangCode": {
        "de": "Ungültiger Sprachcode",
        "en": "Invalid language code",
    },
    "ai.transcript.notAvailable": {
        "de": "Transkript nicht verfügbar",
        "en": "Transcript not available",
    },
}
