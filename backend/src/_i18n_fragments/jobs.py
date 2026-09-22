"""Text fragments for the tool and job routes."""

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
    "translate.documentTooLong": {
        "de": "Dokument zu lang ({chars} Zeichen). Bitte aufteilen (max. {maxChars} Zeichen).",
        "en": "Document too long ({chars} characters). Please split (max {maxChars} characters).",
    },
    "translate.textTooLong": {
        "de": "Text zu lang ({chars} Zeichen). Bitte kürzen (max. {maxChars} Zeichen).",
        "en": "Text too long ({chars} characters). Please shorten (max {maxChars} characters).",
    },
    "translate.textEmpty": {
        "de": "Bitte Text eingeben.",
        "en": "Please enter some text.",
    },
    "translate.noInput": {
        "de": "Bitte Text eingeben oder Datei hochladen.",
        "en": "Please enter text or upload a file.",
    },
    "translate.bothInputs": {
        "de": "Bitte entweder Text eingeben oder eine Datei hochladen, nicht beides.",
        "en": "Please provide either text or a file, not both.",
    },
    "transcription.audioTooLong": {
        "de": "Aufnahme zu lang ({minutes} Minuten). Erlaubt sind höchstens {maxMinutes} Minuten.",
        "en": "Recording too long ({minutes} minutes). The maximum is {maxMinutes} minutes.",
    },

    # ── glossary (terminology, per user) ──────────────────────────────────────
    "glossary.tooMany": {
        "de": "Maximal {max} Glossare pro Person erlaubt.",
        "en": "At most {max} glossaries per user allowed.",
    },
    "glossary.notFound": {
        "de": "Glossar nicht gefunden.",
        "en": "Glossary not found.",
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
    "transcription.invalidProvider": {
        "de": "Ungültiger Anbieter ausgewählt",
        "en": "Invalid provider selected",
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
    "summary.invalidProvider": {
        "de": "Ungültiger Anbieter ausgewählt",
        "en": "Invalid provider selected",
    },
    "summary.fileTooLarge": {
        "de": "Datei zu groß",
        "en": "File too large",
    },
    "summary.documentTooLong": {
        "de": "Dokument zu lang ({chars} Zeichen). Bitte aufteilen (max. {maxChars} Zeichen).",
        "en": "Document too long ({chars} characters). Please split (max {maxChars} characters).",
    },
    "summary.materialTooLarge": {
        "de": "Deine Quellen enthalten zusammen {chars} Zeichen. Möglich sind {max}. Bitte nimm weniger oder kürzere Quellen.",
        "en": "Your sources carry {chars} characters together. The limit is {max}. Please use fewer or shorter sources.",
    },
    "summary.sourceTooLarge": {
        "de": "\"{name}\" enthält {chars} Zeichen. Je Dokument sind {max} möglich.",
        "en": "\"{name}\" carries {chars} characters. Per document {max} are possible.",
    },
    "summary.sourceOnlyImages": {
        "de": "In \"{name}\" steht kein lesbarer Text, die Seiten bestehen nur aus Bildern. Bitte nimm eine Fassung mit Textebene.",
        "en": "There is no readable text in \"{name}\", its pages are images only. Please use a version with a text layer.",
    },
    "summary.sourceTooManyPages": {
        "de": "\"{name}\" hat {pages} Seiten. Je Dokument sind {max} möglich.",
        "en": "\"{name}\" has {pages} pages. Per document {max} are possible.",
    },
    "summary.modelWindowTooSmall": {
        "de": "\"{name}\" hat {chars} Zeichen und wird in einem Stück gelesen. Das gewählte Modell fasst {window} Token, nötig wären {needed}. Bitte wähle ein größeres Modell oder eine kürzere Datei.",
        "en": "\"{name}\" carries {chars} characters and is read in one piece. The chosen model holds {window} tokens, {needed} would be needed. Please pick a larger model or a shorter file.",
    },
    "summary.tooManySources": {
        "de": "Höchstens {max} Quellen je Zusammenfassung.",
        "en": "At most {max} sources per summary.",
    },
    "summary.noFiles": {
        "de": "Bitte wähle mindestens eine Datei aus.",
        "en": "Please choose at least one file.",
    },
    "summary.contentTooShort": {
        "de": "Zu wenig Text ({words} Wörter, mindestens {min}).",
        "en": "Too little text ({words} words, at least {min}).",
    },
    "summary.templateMissing": {
        "de": "Diese Vorlage gibt es nicht.",
        "en": "This build plan does not exist.",
    },
    "summary.jobLabel": {
        "de": "{name} und {more} weitere",
        "en": "{name} and {more} more",
    },
    # Cover page and table of contents of the Word file. The language here follows the
    # document, not the person who started the run: whoever reads it only sees the document.
    "summary.docxToc": {
        "de": "Inhaltsverzeichnis",
        "en": "Table of contents",
    },
    "summary.docxDisclaimer": {
        "de": "Mit künstlicher Intelligenz erstellt. Bitte vor der Verwendung auf Richtigkeit und Vollständigkeit prüfen.",
        "en": "Created with artificial intelligence. Please check it for accuracy and completeness before use.",
    },

    # ── image ────────────────────────────────────────────────────────────────
    "image.invalidSize": {
        "de": "Ungültige Bildgröße",
        "en": "Invalid image size",
    },
    "image.invalidProvider": {
        "de": "Ungültiger Anbieter ausgewählt",
        "en": "Invalid provider selected",
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
    "screencast.queueFull": {
        "de": "Du hast bereits {max} Screencast-Jobs in der Warteschlange.",
        "en": "You already have {max} screencast jobs in the queue.",
    },
    "screencast.tooManySlides": {
        "de": "Zu viele Folien ({count}). Maximum: {max} Folien.",
        "en": "Too many slides ({count}). Maximum: {max} slides.",
    },
    "screencast.folienzahlPasstNicht": {
        "de": (
            "Die hochgeladene Datei hat {neu} Folien, die Präsentation in diesem Auftrag hat "
            "{alt}. Skripte und Ton hängen an der Foliennummer, eine andere Anzahl würde alles "
            "verschieben. Bitte nur den Text ändern, keine Folien löschen oder hinzufügen. Soll "
            "es wirklich eine andere Präsentation werden, dann in Schritt 1 neu anfangen."
        ),
        "en": (
            "The uploaded file has {neu} slides, the presentation in this job has {alt}. "
            "Scripts and audio are tied to the slide number, a different count would shift "
            "everything. Please only change the text, do not delete or add slides. If you really "
            "want a different presentation, start over at step 1."
        ),
    },
    "screencast.keineFolieGewaehlt": {
        "de": "Es ist keine Folie für den Screencast ausgewählt.",
        "en": "No slide is selected for the screencast.",
    },
    "screencast.folieUnbekannt": {
        "de": "Die Auswahl nennt eine Folie, die es in dieser Präsentation nicht gibt.",
        "en": "The selection refers to a slide that does not exist in this presentation.",
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

    # ── screencastDemo ───────────────────────────────────────────────────────
    "screencastDemo.scriptsMissing": {
        "de": "Keine Skripte in demo/ gefunden (accepted_scripts.json fehlt)",
        "en": "No scripts found in demo/ (accepted_scripts.json missing)",
    },
    "screencastDemo.videoMissing": {
        "de": "Kein Demo-Video gefunden (output.mp4 fehlt in demo/)",
        "en": "No demo video found (output.mp4 missing in demo/)",
    },
    # ── gemeinsamer Quellen-Eingang der drei Dienste ─────────────────────────
    "summary.noContent": {
        "de": "Ohne Quelle gibt es nichts zusammenzufassen. Bitte lade mindestens eine Datei hoch.",
        "en": "Without a source there is nothing to summarise. Please upload at least one file.",
    },
    "summary.fileUnreadable": {
        "de": "\"{name}\" liess sich nicht lesen. Bitte pruefe die Datei.",
        "en": "\"{name}\" could not be read. Please check the file.",
    },
    "podcast.sourceOnlyImages": {
        "de": "In \"{name}\" steht kein lesbarer Text, die Seiten bestehen nur aus Bildern. Bitte nimm eine Fassung mit Textebene.",
        "en": "There is no readable text in \"{name}\", its pages are images only. Please use a version with a text layer.",
    },
    "praesentation.sourceOnlyImages": {
        "de": "In \"{name}\" steht kein lesbarer Text, die Seiten bestehen nur aus Bildern. Bitte nimm eine Fassung mit Textebene.",
        "en": "There is no readable text in \"{name}\", its pages are images only. Please use a version with a text layer.",
    },
    "praesentation.fileUnreadable": {
        "de": "\"{name}\" liess sich nicht lesen. Bitte pruefe die Datei.",
        "en": "\"{name}\" could not be read. Please check the file.",
    },
}
