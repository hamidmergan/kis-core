"""i18n message fragments for AI Assistant routes."""

MESSAGES: dict[str, dict[str, str]] = {
    # Workspace / module
    "ai.workspace.transcriptTargetLangInvalid": {
        "de": "Ungültige Zielsprache für die Übersetzung",
        "en": "Invalid translation target language",
    },
    "ai.transcript.targetEqualsSource": {
        "de": "Die Zielsprache ist schon die Sprache der Aufnahme",
        "en": "The target language already is the language of the recording",
    },
    "ai.workspace.tourModuleNotDemo": {
        "de": "Nur ein Workspace eines Demo-Kontos kann der Workspace für den Rundgang sein",
        "en": "Only a workspace of a demo account can be the workspace for the guided tour",
    },
    "ai.workspace.diagnosisLanguageInvalid": {
        "de": "Ungültige Sprache für die Sprachdiagnose",
        "en": "Invalid language for the language diagnosis",
    },
    "ai.languageTraining.disabled": {
        "de": "Der Sprachtrainer ist auf dieser Plattform ausgeschaltet",
        "en": "The language trainer is switched off on this platform",
    },
    "ai.languageTraining.off": {
        "de": "Der Sprachtrainer ist für dich ausgeschaltet. Schalte ihn im Profil ein und mach den Sprachtest.",
        "en": "The language trainer is switched off for you. Switch it on in your profile and take the language test.",
    },
    "ai.userSettings.popupTranslateLangInvalid": {
        "de": "Ungültige Zielsprache für die Übersetzung in der Auswahlleiste",
        "en": "Invalid target language for the selection-bar translation",
    },
    "ai.workspace.invalidEnrollCode": {
        "de": "Ungültiger oder abgelaufener Einschreibecode",
        "en": "Invalid or expired enrollment code",
    },
    "ai.demo.notFound": {
        "de": "Dieser Kurs gehört nicht zur Demo",
        "en": "This course is not part of the demo",
    },
    "ai.workspace.maxAccessLinks": {
        "de": "Maximal {max} Einschreibelinks pro Workspace erlaubt. Bitte lösche zuerst einen alten Link.",
        "en": "Maximum {max} enrollment links per workspace allowed. Please delete an old link first.",
    },
    "ai.workspace.maxMembers": {
        "de": "Dieser Workspace hat die Höchstzahl von {max} Mitgliedern erreicht.",
        "en": "This workspace has reached its limit of {max} members.",
    },
    # Sources
    "ai.source.maxPerWorkspace": {
        "de": "Maximal {max} Sources pro {label} erlaubt. Bitte lösche nicht mehr benötigte Sources.",
        "en": "Maximum {max} sources per {label} allowed. Please delete sources you no longer need.",
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
    "ai.source.duplicateName": {
        "de": "Eine Source mit dem Namen \"{name}\" existiert bereits in diesem {label}.",
        "en": "A source named \"{name}\" already exists in this {label}.",
    },
    "ai.source.nameEmpty": {
        "de": "Der Name darf nicht leer sein.",
        "en": "The name must not be empty.",
    },
    "ai.source.nameTooLong": {
        "de": "Der Name darf höchstens {max} Zeichen lang sein.",
        "en": "The name may be at most {max} characters long.",
    },
    "ai.chapter.notFound": {
        "de": "Das Kapitel wurde nicht gefunden.",
        "en": "The chapter was not found.",
    },
    "ai.chapter.nameEmpty": {
        "de": "Der Name des Kapitels darf nicht leer sein.",
        "en": "The chapter name must not be empty.",
    },
    "ai.chapter.nameTooLong": {
        "de": "Der Name des Kapitels darf höchstens {max} Zeichen lang sein.",
        "en": "The chapter name may be at most {max} characters long.",
    },
    "ai.chapter.duplicateName": {
        "de": "Ein Kapitel mit dem Namen \"{name}\" gibt es hier schon.",
        "en": "A chapter named \"{name}\" already exists here.",
    },
    "ai.chapter.tooMany": {
        "de": "Mehr als {max} Kapitel sind nicht möglich.",
        "en": "More than {max} chapters are not possible.",
    },
    "ai.chapter.badDirection": {
        "de": "Richtung muss \"up\" oder \"down\" sein.",
        "en": "Direction must be \"up\" or \"down\".",
    },
    "ai.source.fileTooLargeMb": {
        "de": "Datei zu groß (max {max} MB)",
        "en": "File too large (max {max} MB)",
    },
    "ai.source.tooManyPages": {
        "de": "Dokument hat {pages} Seiten - max. {max} Seiten erlaubt. Bitte teile das Dokument in kleinere Abschnitte auf.",
        "en": "Document has {pages} pages - max. {max} pages allowed. Please split the document into smaller sections.",
    },
    "ai.source.serverBusy": {
        "de": "Der Server verarbeitet gerade zu viele Uploads gleichzeitig. Bitte in einem Moment erneut versuchen.",
        "en": "The server is handling too many uploads at once. Please try again in a moment.",
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
    # Web page as a source.
    "ai.link.invalid": {
        "de": "Das ist kein gültiger Link.",
        "en": "That is not a valid link.",
    },
    "ai.link.forbiddenAddress": {
        "de": "Diese Adresse darf nicht abgerufen werden.",
        "en": "This address must not be fetched.",
    },
    "ai.link.unreachable": {
        "de": "Die Seite antwortet nicht.",
        "en": "The page does not respond.",
    },
    "ai.link.loginRequired": {
        "de": "Die Seite verlangt eine Anmeldung. Seiten hinter Login gehen nicht.",
        "en": "The page requires a login. Pages behind a login do not work.",
    },
    "ai.link.httpError": {
        "de": "Die Seite antwortet mit Fehler {status}.",
        "en": "The page answers with error {status}.",
    },
    "ai.link.tooManyRedirects": {
        "de": "Die Seite leitet zu oft weiter.",
        "en": "The page redirects too often.",
    },
    "ai.link.tooLarge": {
        "de": "Die Seite ist zu groß. Ein großes PDF kannst du direkt hochladen.",
        "en": "The page is too large. A large PDF can be uploaded directly.",
    },
    "ai.link.unsupportedType": {
        "de": "Der Link zeigt weder auf eine Textseite noch auf ein PDF.",
        "en": "The link points neither to a text page nor to a PDF.",
    },
    "ai.link.noText": {
        "de": "Die Seite liefert keinen lesbaren Text.",
        "en": "The page yields no readable text.",
    },
    "ai.link.duplicate": {
        "de": "Dieser Link ist schon im {label}.",
        "en": "This link is already in the {label}.",
    },
    "ai.link.sourceLine": {
        "de": "Quelle: {url}, abgerufen am {date}",
        "en": "Source: {url}, fetched on {date}",
    },
    # Vocabulary cloze built from flashcards.
    "ai.flashcardSet.invalid": {
        "de": "Das gewählte Lernkarten-Set gibt es nicht.",
        "en": "That flashcard set does not exist.",
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
    "ai.schedule.rangeReversed": {
        "de": "Das Ende des Zeitraums liegt vor dem Anfang.",
        "en": "The end of the range is before its start.",
    },
    "ai.schedule.dateRequired": {
        "de": "Ein eigener Termin braucht ein Datum.",
        "en": "Your own entry needs a date.",
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
    # Language diagnosis (one-time CEFR chat assessment)
    "ai.languageDiagnosis.llmUnavailable": {
        "de": "Auswertung aktuell nicht möglich. Bitte später erneut versuchen.",
        "en": "Evaluation unavailable. Please try again later.",
    },
    "ai.languageDiagnosis.invalidResponse": {
        "de": "Auswertung fehlgeschlagen. Bitte erneut versuchen.",
        "en": "Evaluation failed. Please retry.",
    },
    # Deliberately sober, without a single answer there is nothing to praise.
    "ai.languageDiagnosis.allSkipped": {
        "de": "Du hast alle Fragen übersprungen. Dein Niveau steht deshalb auf A1. "
              "Du kannst den Test jederzeit neu machen.",
        "en": "You skipped every question. Your level is therefore set to A1. "
              "You can take the test again at any time.",
    },
    # YouTube video as a source.
    "ai.youtube.invalid": {
        "de": "Das ist kein Link auf ein YouTube-Video.",
        "en": "That is not a link to a YouTube video.",
    },
    "ai.youtube.duplicate": {
        "de": "Dieses Video ist schon im {label}.",
        "en": "This video is already in the {label}.",
    },
    "ai.youtube.notFound": {
        "de": "Unter diesem Link gibt es kein Video.",
        "en": "There is no video at this link.",
    },
    "ai.youtube.notEmbeddable": {
        "de": "Das Video lässt sich nicht einbetten. Es ist privat oder das Einbetten ist gesperrt.",
        "en": "The video cannot be embedded. It is private or embedding is disabled.",
    },
    "ai.youtube.noTimestamps": {
        "de": "Im Transkript fehlen die Zeitstempel. Schalte sie im YouTube-Transkript über das "
              "Drei-Punkte-Menü ein und kopiere den Text neu.",
        "en": "The transcript has no timestamps. Turn them on in the YouTube transcript via the "
              "three-dot menu and copy the text again.",
    },
    "ai.youtube.emptyTranscript": {
        "de": "Das Transkript enthält keinen Text.",
        "en": "The transcript contains no text.",
    },
    "ai.youtube.tooLong": {
        "de": "Das Transkript ist zu lang.",
        "en": "The transcript is too long.",
    },
    "ai.youtube.videoTooLong": {
        "de": "Das Video ist {minutes} Minuten lang, erlaubt sind höchstens {max} Minuten. "
              "Bitte füge nur den Teil des Transkripts ein, um den es geht.",
        "en": "The video is {minutes} minutes long, at most {max} minutes are allowed. "
              "Please paste only the part of the transcript you need.",
    },
    "ai.youtube.noFile": {
        "de": "Zu einem YouTube-Video gibt es keine Datei.",
        "en": "A YouTube video has no file.",
    },
    "ai.link.useYoutube": {
        "de": "Das ist ein YouTube-Link. Nutze dafür den Abschnitt YouTube-Video.",
        "en": "That is a YouTube link. Use the YouTube video section for it.",
    },
}
