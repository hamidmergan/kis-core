"""i18n message fragments for tool/job routes.

Auto-loaded by `src.i18n._load_fragments()`. Keys group by the route area
(`translate`, `tts`, `image`, `summary`, `screencast`,
`job`, `auth`).
"""

MESSAGES: dict[str, dict[str, str]] = {
    # ── translate ────────────────────────────────────────────────────────────
    "translate.deeplKeyMissing": {
        "de": "DeepL API Key fehlt",
        "en": "DeepL API key missing",
    },
    "translate.pptxError": {
        "de": "PPTX-Übersetzungsfehler: {error}",
        "en": "PPTX translation error: {error}",
    },
    "translate.pptxProcessingError": {
        "de": "PPTX-Verarbeitungsfehler: {error}",
        "en": "PPTX processing error: {error}",
    },
    "translate.unsupportedFormat": {
        "de": "Nur .docx, .pptx, .md, .tex oder .txt erlaubt",
        "en": "Only .docx, .pptx, .md, .tex or .txt allowed",
    },
    "file.tooLargeMb500": {
        "de": "Datei zu groß (max 500 MB)",
        "en": "File too large (max 500 MB)",
    },
    "translate.documentTooLong": {
        "de": "Dokument zu lang ({chars} Zeichen). Bitte aufteilen (max. {maxChars} Zeichen).",
        "en": "Document too long ({chars} characters). Please split (max {maxChars} characters).",
    },

    # ── transcription ────────────────────────────────────────────────────────
    "transcription.unsupportedFormat": {
        "de": "Nur {formats} erlaubt",
        "en": "Only {formats} allowed",
    },
    "transcription.invalidTask": {
        "de": "Ungültiger Task: {task}",
        "en": "Invalid task: {task}",
    },
    "transcription.invalidFormat": {
        "de": "Ungültiges Format: {format}",
        "en": "Invalid format: {format}",
    },

    # ── tts ──────────────────────────────────────────────────────────────────
    "tts.unsupportedFormat": {
        "de": "Nur .docx, .md oder .txt erlaubt",
        "en": "Only .docx, .md or .txt allowed",
    },
    "tts.unsupportedFileType": {
        "de": "Dateityp wird nicht unterstützt",
        "en": "File type not supported",
    },
    "tts.documentTooLong": {
        "de": "Dokument zu lang ({chars} Zeichen). Bitte aufteilen (max. {maxChars} Zeichen).",
        "en": "Document too long ({chars} characters). Please split (max {maxChars} characters).",
    },
    "tts.textTooLong": {
        "de": "Text zu lang ({chars} Zeichen). Bitte kürzen (max. {maxChars} Zeichen).",
        "en": "Text too long ({chars} characters). Please shorten (max {maxChars} characters).",
    },
    "tts.textEmpty": {
        "de": "Bitte Text eingeben.",
        "en": "Please enter some text.",
    },
    "tts.noInput": {
        "de": "Bitte Text eingeben oder Datei hochladen.",
        "en": "Please enter text or upload a file.",
    },
    "tts.bothInputs": {
        "de": "Bitte entweder Text eingeben oder eine Datei hochladen, nicht beides.",
        "en": "Please provide either text or a file, not both.",
    },
    "tts.providerUnavailable": {
        "de": "TTS-Anbieter ist nicht verfügbar.",
        "en": "TTS provider is not available.",
    },
    "tts.providerNotFound": {
        "de": "TTS-Anbieter nicht gefunden oder nicht konfiguriert.",
        "en": "TTS provider not found or not configured.",
    },
    # ── summary ──────────────────────────────────────────────────────────────
    "summary.unsupportedFormat": {
        "de": "Nur {formats} erlaubt",
        "en": "Only {formats} allowed",
    },
    "summary.invalidOutputFormat": {
        "de": "output_format muss 'txt', 'md' oder 'html' sein",
        "en": "output_format must be 'txt', 'md' or 'html'",
    },
    "summary.fileTooLarge": {
        "de": "Datei zu groß",
        "en": "File too large",
    },
    "summary.documentTooLong": {
        "de": "Dokument zu lang ({chars} Zeichen). Bitte aufteilen (max. {maxChars} Zeichen).",
        "en": "Document too long ({chars} characters). Please split (max {maxChars} characters).",
    },

    # ── image ────────────────────────────────────────────────────────────────
    "image.invalidSize": {
        "de": "Ungültige Bildgröße",
        "en": "Invalid image size",
    },
    "image.empty": {
        "de": "Bild ist leer",
        "en": "Image is empty",
    },
    "image.tooLarge": {
        "de": "Bild zu groß (max 10 MB)",
        "en": "Image too large (max 10 MB)",
    },

    # ── auth ─────────────────────────────────────────────────────────────────
    "auth.invalidCredentials": {
        "de": "Ungültige Zugangsdaten",
        "en": "Invalid credentials",
    },
    "auth.accountNotActivated": {
        "de": "Konto nicht aktiviert",
        "en": "Account not activated",
    },

    # ── me ───────────────────────────────────────────────────────────────────
    "user.notFound": {
        "de": "Benutzer nicht gefunden",
        "en": "User not found",
    },

    # ── job (shared, additional keys) ────────────────────────────────────────
    "job.notCompleted": {
        "de": "Job noch nicht abgeschlossen",
        "en": "Job not completed yet",
    },
    "job.noDownloadAvailable": {
        "de": "Kein Download für diesen Job",
        "en": "No download for this job",
    },
    "job.fileExpired": {
        "de": "Datei nicht mehr vorhanden (abgelaufen)",
        "en": "File no longer available (expired)",
    },
    "job.resultLoadFailed": {
        "de": "Ergebnis konnte nicht geladen werden",
        "en": "Result could not be loaded",
    },
    "job.retryOnlyTtsScreencast": {
        "de": "Retry nur für TTS- und Screencast-Jobs verfügbar",
        "en": "Retry only available for TTS and screencast jobs",
    },
    "job.alreadySuccessful": {
        "de": "Job bereits erfolgreich abgeschlossen",
        "en": "Job already completed successfully",
    },
    "job.alreadyRunning": {
        "de": "Job läuft bereits",
        "en": "Job already running",
    },
    "job.inputFileExpired": {
        "de": "Eingabedatei nicht mehr vorhanden (abgelaufen)",
        "en": "Input file no longer available (expired)",
    },
    "job.paramsNotSaved": {
        "de": "Job-Parameter nicht gespeichert - bitte neuen Job starten",
        "en": "Job parameters not saved - please start a new job",
    },
    "job.renderParamsExpired": {
        "de": "Render-Parameter nicht mehr vorhanden - bitte neuen Screencast starten",
        "en": "Render parameters no longer available - please start a new screencast",
    },
    "job.demoParamsExpired": {
        "de": "Demo-Parameter nicht mehr vorhanden (abgelaufen)",
        "en": "Demo parameters no longer available (expired)",
    },
    "job.featureNotConfigured": {
        "de": "Diese Funktion ist nicht konfiguriert. Bitte Admin kontaktieren.",
        "en": "This feature is not configured. Please contact your admin.",
    },

    # ── screencast ───────────────────────────────────────────────────────────
    "screencast.onlyPptx": {
        "de": "Nur .pptx erlaubt",
        "en": "Only .pptx allowed",
    },
    "file.tooLargeMb200": {
        "de": "Datei zu groß (max 200 MB)",
        "en": "File too large (max 200 MB)",
    },
    "screencast.queueFull": {
        "de": "Du hast bereits {max} Screencast-Jobs in der Warteschlange.",
        "en": "You already have {max} screencast jobs in the queue.",
    },
    "screencast.tooManySlides": {
        "de": "Zu viele Folien ({count}). Maximum: {max} Folien.",
        "en": "Too many slides ({count}). Maximum: {max} slides.",
    },
    "screencast.pptxUnavailable": {
        "de": "PPTX nicht mehr verfügbar",
        "en": "PPTX no longer available",
    },
    "screencast.pptxNotFound": {
        "de": "PPTX nicht gefunden",
        "en": "PPTX not found",
    },
    "screencast.pptxExpired": {
        "de": "PPTX nicht mehr vorhanden (abgelaufen)",
        "en": "PPTX no longer available (expired)",
    },
    "screencast.translateJobNotFound": {
        "de": "Translate-Job nicht gefunden",
        "en": "Translate job not found",
    },
    "screencast.notReadyForRender": {
        "de": "Job ist nicht bereit zum Rendern",
        "en": "Job is not ready for rendering",
    },
    "screencast.jobFilesGone": {
        "de": "Job-Dateien nicht mehr vorhanden. Bitte neue Übersetzung starten.",
        "en": "Job files no longer available. Please start a new translation.",
    },
    "screencast.alreadyProcessing": {
        "de": "Dieser Job wird bereits verarbeitet.",
        "en": "This job is already being processed.",
    },
    "screencast.noScripts": {
        "de": "Keine Skripte übergeben",
        "en": "No scripts provided",
    },
    "screencast.scriptTooLong": {
        "de": "Das Skript ist zu lang ({chars} Zeichen). Maximum: {maxChars} Zeichen.",
        "en": "The script is too long ({chars} characters). Maximum: {maxChars} characters.",
    },
    "screencast.noSlideTexts": {
        "de": "Keine Folientexte übergeben",
        "en": "No slide texts provided",
    },
    "screencast.scriptGenerationFailed": {
        "de": "Skript-Generierung fehlgeschlagen: {error}",
        "en": "Script generation failed: {error}",
    },
    "screencast.slideNotFound": {
        "de": "Folie {slide} nicht gefunden",
        "en": "Slide {slide} not found",
    },
}
