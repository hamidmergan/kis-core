"""Text fragments of the backend, the language comes from the request header."""

from fastapi import Header, Query

SUPPORTED_LOCALES = ("de", "en")
DEFAULT_LOCALE = "de"

# Translate-tool language codes (DeepL format).
TRANSLATE_LANGUAGES: tuple[str, ...] = (
    "DE", "EN-US",
)
DEFAULT_TRANSLATE_SOURCE = "DE"
DEFAULT_TRANSLATE_TARGET = "EN-US"

# The one place for the languages transcripts are translated into.
TRANSCRIPT_LANGUAGES: dict[str, dict[str, str]] = {
    "de": {"deepl": "DE",    "name": "German"},
    "en": {"deepl": "EN-US", "name": "English"},
}
DEFAULT_TRANSCRIPT_TARGET = "en"
# The language a course room runs its assessment in, German by default.
DEFAULT_DIAGNOSIS_LANGUAGE = "de"
# Language flashcards, quiz, data table and mind map are written in.
DEFAULT_LEARNING_TOOLS_LANGUAGE = "de"


# All visible texts of the backend, always add them in both languages.
MESSAGES: dict[str, dict[str, str]] = {
    # Auth
    "auth.notAuthenticated": {
        "de": "Nicht authentifiziert",
        "en": "Not authenticated",
    },
    "auth.adminRequired": {
        "de": "Admin-Zugriff erforderlich",
        "en": "Admin access required",
    },
    "auth.aiaForbidden": {
        "de": "Du hast keinen Zugriff auf den AIA-Bereich.",
        "en": "You do not have access to the AIA area.",
    },
    "auth.workspaceCreateForbidden": {
        "de": "Du darfst keine neuen Workspaces erstellen.",
        "en": "You may not create new workspaces.",
    },
    "auth.toolForbidden": {
        "de": "Du darfst diesen Dienst nicht nutzen.",
        "en": "You may not use this service.",
    },
    "auth.permissionRequired": {
        "de": "Dir fehlt die Berechtigung für diesen Bereich.",
        "en": "You do not have permission for this area.",
    },
    "auth.settingFieldForbidden": {
        "de": "Du darfst die Einstellung „{field}“ nicht ändern.",
        "en": "You may not change the setting “{field}”.",
    },
    # You can only grant what you hold yourself.
    "auth.grantBeyondOwn": {
        "de": "Du kannst nur Rechte vergeben, die du selbst hast.",
        "en": "You can only grant permissions you hold yourself.",
    },
    "admin.role.nameTaken": {
        "de": "Die Rolle „{name}“ gibt es schon.",
        "en": "The role “{name}” already exists.",
    },
    # Common errors (broadly reused across feature routes)
    "workspace.notFound": {"de": "Workspace nicht gefunden", "en": "Workspace not found"},
    "workspace.accessDenied": {"de": "Kein Zugriff", "en": "Access denied"},
    # An inactive course room is not a missing right but a closed room.
    "workspace.inactive": {
        "de": "Dieser Workspace ist gerade nicht freigegeben.",
        "en": "This workspace is currently not open.",
    },
    "job.notFound": {"de": "Job nicht gefunden", "en": "Job not found"},
    "job.accessDenied": {
        "de": "Kein Zugriff auf diesen Job",
        "en": "No access to this job",
    },
    "job.invalidUuid": {"de": "Ungültige Job-UUID", "en": "Invalid job UUID"},
    "job.parallelRunning": {
        "de": "Job läuft bereits (parallel gestartet)",
        "en": "Job already running (started in parallel)",
    },
    "job.notInputState": {
        "de": "Job ist nicht im Eingabe-Status",
        "en": "Job is not in input state",
    },
    "job.dataUnavailable": {
        "de": "Job-Daten nicht mehr verfügbar - bitte neuen Screencast starten",
        "en": "Job data no longer available - please start a new screencast",
    },
    "job.timeoutRetry": {
        "de": "Zeitlimit überschritten.",
        "en": "Time limit exceeded.",
    },
    "job.watchdogStuck": {
        "de": "Der Auftrag hat sich nicht mehr gemeldet.",
        "en": "The job stopped reporting progress.",
    },
    "job.pausedAfterAttempts": {
        "de": "Nach {n} Anläufen angehalten. Letzter Fehler: {error}",
        "en": "Paused after {n} attempts. Last error: {error}",
    },
    "job.serverRestarted": {
        "de": "Der Server wurde neu gestartet.",
        "en": "The server was restarted.",
    },
    "job.watchdogStaleAwaiting": {
        "de": "Auftrag abgelaufen, es kam keine Eingabe mehr.",
        "en": "Job expired, no further input was received.",
    },
    "job.upstreamBusy": {
        "de": "Die KI steht wegen begrenzter Rechenkapazität nicht immer zur Verfügung. Bitte versuche es später noch einmal.",
        "en": "The AI is not always available because computing capacity is limited. Please try again later.",
    },
    "job.providerRefused": {
        "de": "Der KI-Anbieter hat die Anfrage abgelehnt. Wähle einen anderen Anbieter oder versuche es später noch einmal.",
        "en": "The AI provider turned the request down. Pick another provider or try again later.",
    },
    "job.unexpectedError": {
        "de": "Unerwarteter Fehler: {error}",
        "en": "Unexpected error: {error}",
    },
    "summary.contentTooShort": {
        "de": "Inhalt zu kurz ({words} Wörter). Mindestens {min} Wörter erforderlich.",
        "en": "Content too short ({words} words). At least {min} words required.",
    },
    "summary.contentTooLongHint": {
        "de": "\n\n⚠️ Hinweis: Der Inhalt war sehr umfangreich. Die Zusammenfassung könnte unvollständig sein.",
        "en": "\n\n⚠️ Note: The content was very long. The summary may be incomplete.",
    },
    "ai.source.pdfNoReadableText": {
        "de": "Das PDF enthält keinen lesbaren Text. Gescannte PDFs werden aktuell nicht unterstützt. Bitte konvertiere das PDF zuerst mit einem OCR-Tool (z.B. Adobe Acrobat oder online unter smallpdf.com).",
        "en": "The PDF does not contain readable text. Scanned PDFs are not supported. Please convert the PDF with an OCR tool first (e.g. Adobe Acrobat or online via smallpdf.com).",
    },
    "file.contentMismatch": {
        "de": "Dateiinhalt passt nicht zur Endung. Möglicherweise wurde die Datei umbenannt oder ist beschädigt.",
        "en": "File content does not match the extension. The file may have been renamed or is corrupted.",
    },
    "file.textNotUtf8": {
        "de": "Textdatei muss UTF-8-kodiert sein.",
        "en": "Text file must be UTF-8 encoded.",
    },
    # Quota labels (interpolated into quota.limitReached)
    "quota.label.tts": {"de": "Text in Audio", "en": "Text to audio"},
    "quota.label.summary": {"de": "Report", "en": "Report"},
    "quota.label.translate": {"de": "Dokumentenübersetzung", "en": "Document translation"},
    "quota.label.transcription": {"de": "Transkription", "en": "Transcription"},
    "quota.label.image_generate": {"de": "Bild-Generierung", "en": "Image generation"},
    "quota.label.image_edit": {"de": "Bild-Bearbeitung", "en": "Image editing"},
    "quota.label.image_analyze": {"de": "Bild-Analyse", "en": "Image analysis"},
    "quota.label.screencast": {"de": "Screencast", "en": "Screencast"},
    "quota.label.podcast": {"de": "Podcast", "en": "Podcast"},
    "quota.label.aia_generate": {"de": "KI-Tutor: Generierung", "en": "AI tutor: generation"},
    "source.notFound": {"de": "Source nicht gefunden", "en": "Source not found"},
    "entry.notFound": {"de": "Eintrag nicht gefunden", "en": "Entry not found"},
    "set.notFound": {"de": "Set nicht gefunden", "en": "Set not found"},
    "title.empty": {"de": "Der Name darf nicht leer sein", "en": "The name must not be empty"},
    "flashcards.noExampleSentence": {
        "de": "Zu dieser Karte gibt es keinen Beispielsatz",
        "en": "This card has no example sentence",
    },
    "flashcards.speechOnly": {
        "de": "Der Lautsprecher ist nur für Lernkarten-Übungen verfügbar",
        "en": "Speech is only available for flashcard exercises",
    },
    "set.retryNotFailed": {
        "de": "Diese Übung wird gerade erstellt oder ist schon fertig",
        "en": "This exercise is being created right now or is already finished",
    },
    "grammar.typeInvalid": {
        "de": "Thema ist in diesem Workspace nicht verfügbar",
        "en": "This topic is not available in this workspace",
    },
    "grammar.topicNotFound": {
        "de": "Thema nicht gefunden",
        "en": "Topic not found",
    },
    "grammar.topicNameEmpty": {
        "de": "Bitte gib ein Thema ein, zum Beispiel „Konjunktiv II“",
        "en": "Please enter a topic, for example “Konjunktiv II”",
    },
    "grammar.topicNeedsExample": {
        "de": "Bitte lass mindestens ein Musterpaar stehen",
        "en": "Please keep at least one pattern pair",
    },
    "grammar.topicExists": {
        "de": "Dieses Thema gibt es hier schon",
        "en": "This topic already exists here",
    },
    "grammar.topicServiceDown": {
        "de": "Der KI-Anbieter antwortet gerade nicht. Bitte versuche es in ein paar "
              "Minuten noch einmal, dein Thema ist in Ordnung.",
        "en": "The AI provider is not responding right now. Please try again in a few "
              "minutes, your topic is fine.",
    },
    "grammar.topicNotRecognized": {
        "de": "Daraus lässt sich kein Grammatikthema machen. Versuche es mit einer "
              "grammatischen Form, zum Beispiel „Konjunktiv II“ oder „Passiv Präteritum“.",
        "en": "This does not describe a grammar topic. Try a grammatical form such as "
              "“past passive” or “conditional”.",
    },
    "grammar.answerEmpty": {
        "de": "Bitte schreibe zuerst eine Antwort",
        "en": "Please write an answer first",
    },
    "note.notFound": {"de": "Notiz nicht gefunden", "en": "Note not found"},
    "mindmap.notFound": {"de": "Mindmap nicht gefunden", "en": "Mindmap not found"},
    "audio.notFound": {
        "de": "Audio nicht gefunden (abgelaufen oder ungültige ID)",
        "en": "Audio not found (expired or invalid ID)",
    },
    "file.nameMissing": {"de": "Dateiname fehlt", "en": "Filename missing"},
    "file.empty": {"de": "Datei ist leer", "en": "File is empty"},
    "file.tooLargeMb": {
        "de": "Datei zu groß (max {max} MB)",
        "en": "File too large (max {max} MB)",
    },
    "file.invalidPptxBase64": {
        "de": "Ungültige PPTX-Daten (Base64)",
        "en": "Invalid PPTX data (Base64)",
    },
    "file.onlyPngJpg": {"de": "Nur PNG oder JPG erlaubt", "en": "Only PNG or JPG allowed"},
    "prompt.empty": {
        "de": "Prompt darf nicht leer sein",
        "en": "Prompt must not be empty",
    },
    "date.invalidExpiresAt": {
        "de": "Ungültiges Datumsformat für expires_at",
        "en": "Invalid date format for expires_at",
    },
    "scheduleEntry.invalidType": {
        "de": "Typ muss 'deadline' oder 'termin' sein",
        "en": "Type must be 'deadline' or 'termin'",
    },
    # Podcast
    "podcast.badParams": {
        "de": "Diese Einstellungen kann der Podcast nicht verwenden.",
        "en": "The podcast cannot use these settings.",
    },
    "podcast.badCast": {
        "de": "Jede Person braucht einen Namen, eine Rolle und eine Stimme.",
        "en": "Every person needs a name, a role and a voice.",
    },
    "podcast.invalidProvider": {
        "de": "Ungültiger KI-Anbieter ausgewählt",
        "en": "Invalid AI provider selected",
    },
    "podcast.noContent": {
        "de": "Ohne Material gibt es nichts zu erzählen.",
        "en": "Without material there is nothing to tell.",
    },
    "podcast.unsupportedFormat": {
        "de": "Nur {formats} lassen sich lesen.",
        "en": "Only {formats} can be read.",
    },
    "podcast.fileUnreadable": {
        "de": "Die Datei {name} lässt sich nicht lesen.",
        "en": "The file {name} cannot be read.",
    },
    "podcast.queueFull": {
        "de": "Du hast schon {max} Podcasts offen. Schließe einen ab, dann geht es weiter.",
        "en": "You already have {max} podcasts open. Finish one, then you can continue.",
    },
    "job.tooManyOpen": {
        "de": "Du hast gerade zu viele Aufträge laufen. Warte, bis einer fertig ist.",
        "en": "Too many of your jobs are running. Wait until one is finished.",
    },
    "podcast.sourceOnlyImages": {
        "de": "In {name} steckt kein Text, nur Bilder.",
        "en": "{name} holds no text, only pictures.",
    },
    "podcast.materialTooLarge": {
        "de": "Deine Materialien enthalten zusammen {chars} Zeichen. Möglich sind {max}. Bitte nimm weniger oder kürzere Materialien.",
        "en": "Your sources carry {chars} characters together. The limit is {max}. Please use fewer or shorter sources.",
    },
    "podcast.sourceMissing": {
        "de": "Dieses Material gibt es im Workspace nicht.",
        "en": "This source does not exist in the workspace.",
    },
    "podcast.sourceNotReady": {
        "de": "{name} wird noch verarbeitet.",
        "en": "{name} is still being processed.",
    },
    "podcast.tooManySources": {
        "de": "Höchstens {max} Materialien je Podcast.",
        "en": "At most {max} sources per podcast.",
    },
    "podcast.uploadsTooLarge": {
        "de": "Alle Dateien zusammen höchstens {max} MB.",
        "en": "All files together at most {max} MB.",
    },
    "podcast.running": {
        "de": "Dieser Podcast arbeitet gerade.",
        "en": "This podcast is working right now.",
    },
    "podcast.emptyScript": {
        "de": "Das Skript hat keinen einzigen Beitrag.",
        "en": "The script has no contribution at all.",
    },
    "podcast.tooManyLines": {
        "de": "Zu viele Beiträge ({lines}). Erlaubt sind höchstens {max}.",
        "en": "Too many contributions ({lines}). At most {max} are allowed.",
    },
    "podcast.scriptTooLong": {
        "de": "Das Skript ist zu lang ({chars} Zeichen). Erlaubt sind höchstens {maxChars}.",
        "en": "The script is too long ({chars} characters). At most {maxChars} are allowed.",
    },
    "podcast.selfWritten": {
        "de": "Eigenes Skript",
        "en": "Own script",
    },
    "podcast.scriptFailed": {
        "de": "Das Skript ließ sich nicht schreiben. Versuch es mit weniger Material noch einmal.",
        "en": "The script could not be written. Try again with less material.",
    },
    "podcast.renderFailed": {
        "de": "Die Vertonung ist fehlgeschlagen.",
        "en": "The voicing failed.",
    },
    "podcast.lineFailed": {
        "de": "Beitrag {n} konnte nicht vertont werden. Alles davor bleibt erhalten.",
        "en": "Line {n} could not be voiced. Everything before it stays.",
    },
    # Interpreter
    "interpreter.badTarget": {
        "de": "Diese Sprache kennt der Dolmetscher nicht.",
        "en": "The interpreter does not know this language.",
    },
    "interpreter.noProvider": {
        "de": "Kein Übersetzungsanbieter eingerichtet.",
        "en": "No translation provider is configured.",
    },
    "interpreter.ended": {
        "de": "Das Gespräch ist beendet.",
        "en": "The conversation has ended.",
    },
    "interpreter.full": {
        "de": "Das Gespräch ist voll. Starte ein neues Gespräch.",
        "en": "This conversation is full. Start a new one.",
    },
    "interpreter.sessionUnknown": {
        "de": "Dieses Gespräch gibt es nicht.",
        "en": "This conversation does not exist.",
    },
    "interpreter.audioTooLarge": {
        "de": "Die Aufnahme ist zu groß.",
        "en": "The recording is too large.",
    },
    "interpreter.noStt": {
        "de": "Kein Anbieter für Spracherkennung eingerichtet.",
        "en": "No speech recognition provider is configured.",
    },
    "interpreter.sttFailed": {
        "de": "Die Spracherkennung ist gerade nicht möglich.",
        "en": "Speech recognition is not available right now.",
    },
    "interpreter.failed": {
        "de": "Die Übersetzung ist gerade nicht möglich.",
        "en": "Translation is not available right now.",
    },
    "translate.invalidProvider": {
        "de": "Ungültiger Übersetzungs-Provider",
        "en": "Invalid translation provider",
    },
    "glossary.notProvided": {
        "de": "Kein Glossar vorhanden",
        "en": "No glossary provided",
    },
    "screencast.noSlides": {
        "de": "Keine Slides in der Präsentation gefunden",
        "en": "No slides found in the presentation",
    },
    # Provider configuration errors
    "llm.notConfigured": {
        "de": "Kein LLM-Provider konfiguriert",
        "en": "No LLM provider configured",
    },
    # Rate limiting / burst block
    "rateLimit.blocked": {
        "de": "Chat ist bis {time} Uhr gesperrt (zu viele Anfragen in kurzer Zeit). Bitte später erneut versuchen.",
        "en": "Chat is locked until {time} (too many requests in a short time). Please try again later.",
    },
    "rateLimit.uploadHourly": {
        "de": "Stunden-Limit erreicht ({limit} Uploads pro Stunde). Erneut versuchen in ~{minutes} Min.",
        "en": "Hourly limit reached ({limit} uploads per hour). Try again in ~{minutes} min.",
    },
    "admin.settings.deleteAfterDaysOutOfRange": {
        "de": "Die Frist bis zum Löschen muss zwischen {min} und {max} Tagen liegen.",
        "en": "The grace period before deletion must be between {min} and {max} days.",
    },
    "admin.settings.maxSourcesOutOfRange": {
        "de": "Materialien-Limit muss zwischen {min} und {max} liegen.",
        "en": "Source limit must be between {min} and {max}.",
    },
    "admin.settings.contextBudgetOutOfRange": {
        "de": "Kontext-Budget muss zwischen {min} und {max} Zeichen liegen.",
        "en": "Context budget must be between {min} and {max} characters.",
    },
    "admin.settings.toolContextBudgetOutOfRange": {
        "de": "Das Kontext-Budget der Tools muss zwischen {min} und {max} Zeichen liegen.",
        "en": "Tools context budget must be between {min} and {max} characters.",
    },
    "admin.settings.learningToolsLanguageUnknown": {
        "de": "Unbekannte Sprache für die Tools.",
        "en": "Unknown language for the tools.",
    },
    "admin.settings.summaryBatchOutOfRange": {
        "de": "Zusammenfassungs-Häppchen muss zwischen {min} und {max} Zeichen liegen.",
        "en": "Summary batch must be between {min} and {max} characters.",
    },
    "admin.settings.numberOutOfRange": {
        "de": "Der Wert für {field} muss zwischen {min} und {max} liegen.",
        "en": "The value for {field} must be between {min} and {max}.",
    },
    "admin.settings.maxPagesOutOfRange": {
        "de": "Maximale Seiten pro Material muss zwischen {min} und {max} liegen.",
        "en": "Max pages per source must be between {min} and {max}.",
    },
    "admin.settings.toolLimitOutOfRange": {
        "de": "Der Wert muss zwischen {min} und {max} liegen.",
        "en": "The value must be between {min} and {max}.",
    },
    "admin.settings.flashcardVoiceProviderInvalid": {
        "de": "Anbieter für die Aussprache ist keine gültige Nummer",
        "en": "The pronunciation provider is not a valid id",
    },
    # The four concurrency messages went with their input fields.
    "admin.providers.requiredFields": {
        "de": "Name und Base-URL sind Pflicht.",
        "en": "Name and base URL are required.",
    },
    "admin.providers.unknownProtocol": {
        "de": "Unbekanntes Protokoll: {protocol}",
        "en": "Unknown protocol: {protocol}",
    },
    "admin.providers.nameTaken": {
        "de": "Ein Anbieter mit dem Namen \"{name}\" existiert bereits.",
        "en": "A provider with the name \"{name}\" already exists.",
    },
    "admin.providers.notFound": {
        "de": "Anbieter nicht gefunden.",
        "en": "Provider not found.",
    },
    "admin.providers.unknownCapability": {
        "de": "Unbekannte Funktion(en): {items}",
        "en": "Unknown capability/ies: {items}",
    },
    "admin.providers.unknownFeature": {
        "de": "Unbekannte Funktion: {feature}",
        "en": "Unknown feature: {feature}",
    },
    "admin.providers.userChoiceNotSupported": {
        "de": "Funktion {feature} unterstützt keine Nutzer-Auswahl.",
        "en": "Feature {feature} does not support a user-choice list.",
    },
    "admin.providers.userChoiceUnknownProvider": {
        "de": "Anbieter {provider_id} aus der Auswahl existiert nicht.",
        "en": "Provider {provider_id} from the choice list does not exist.",
    },
    "admin.providers.samplingNotSupported": {
        "de": "Funktion {feature} arbeitet nicht mit Temperatur und top_p.",
        "en": "Feature {feature} does not use temperature or top_p.",
    },
    "admin.providers.samplingOutOfRange": {
        "de": "{feld} muss zwischen {min} und {max} liegen.",
        "en": "{feld} must be between {min} and {max}.",
    },
    "admin.providers.windowNoModel": {
        "de": "Ohne Modellnamen gibt es kein Kontextfenster.",
        "en": "A context window needs a model name.",
    },
    "admin.providers.windowOutOfRange": {
        "de": "Das Kontextfenster muss zwischen {min} und {max} Token liegen.",
        "en": "The context window must be between {min} and {max} tokens.",
    },
    "admin.providers.testNoProvider": {
        "de": "Kein Anbieter für diese Funktion ausgewählt.",
        "en": "No provider selected for this feature.",
    },
    "admin.providers.concurrencyUnknownBucket": {
        "de": "Unbekanntes Feld für Obergrenzen: {items}",
        "en": "Unknown concurrency field: {items}",
    },
    "admin.providers.concurrencyOutOfRange": {
        "de": "Die Obergrenze für {bucket} muss eine ganze Zahl zwischen {min} und {max} sein.",
        "en": "The concurrency limit for {bucket} must be a whole number between {min} and {max}.",
    },
    "admin.providers.fallbackNotSupported": {
        "de": "Für {feature} gibt es keinen Rückfall.",
        "en": "Feature {feature} does not support a fallback.",
    },
    "admin.providers.fallbackSameAsPrimary": {
        "de": "Der Rückfall muss ein anderer Anbieter sein als die erste Wahl.",
        "en": "The fallback must be a different provider than the first choice.",
    },
    "admin.providers.fallbackUnknownProvider": {
        "de": "Anbieter {provider_id} für den Rückfall existiert nicht.",
        "en": "Fallback provider {provider_id} does not exist.",
    },
    "admin.providers.fallbackDisabled": {
        "de": "Der Anbieter für den Rückfall ist ausgeschaltet.",
        "en": "The fallback provider is disabled.",
    },
    "admin.providers.fallbackProtocol": {
        "de": "Als Rückfall kommt nur ein OpenAI-kompatibler Anbieter in Frage.",
        "en": "Only an OpenAI compatible provider can be a fallback.",
    },
    "admin.providers.fallbackCapability": {
        "de": "Der Anbieter für den Rückfall bietet {capability} nicht an.",
        "en": "The fallback provider does not offer {capability}.",
    },
    "admin.providers.fallbackNoModel": {
        "de": "Für den Rückfall fehlt das Modell.",
        "en": "The fallback needs a model.",
    },
    "admin.providers.fallbackNoVoices": {
        "de": "Der Anbieter für den Rückfall hat keine Stimmen.",
        "en": "The fallback provider has no voices.",
    },
    "admin.providers.fallbackEmbeddingModel": {
        "de": "Beim Embedding muss der Rückfall dasselbe Modell nutzen wie die erste Wahl ({model}).",
        "en": "For embedding the fallback must use the same model as the first choice ({model}).",
    },
    # Quota enforcement
    "quota.limitReached": {
        "de": "Limit erreicht für {label}.",
        "en": "Limit reached for {label}.",
    },
    "quota.resetAt": {
        "de": " Erneut verfügbar ab {time} Uhr.",
        "en": " Available again at {time}.",
    },
    # Glossary extract feedback (returned in response body, not detail)
    "ai.glossary.full": {
        "de": "Glossar voll ({current} / {max}) - entferne Begriffe um neue hinzuzufügen.",
        "en": "Glossary full ({current} / {max}) - remove terms to add new ones.",
    },
    "ai.glossary.noTextSelected": {
        "de": "Kein Text markiert.",
        "en": "No text selected.",
    },
    "ai.glossary.noLearnableTerms": {
        "de": "Keine lernenswerten Begriffe in der Markierung gefunden.",
        "en": "No worthwhile terms found in the selection.",
    },
    "ai.glossary.alreadyKnown": {
        "de": "Die erkannten Begriffe sind bereits im Glossar.",
        "en": "The detected terms are already in the glossary.",
    },
    "ai.glossary.noNewTerms": {
        "de": "Keine neuen lernenswerten Begriffe in der Markierung gefunden.",
        "en": "No new worthwhile terms found in the selection.",
    },
    "ai.glossary.added": {
        "de": "{count} Begriffe zum Glossar hinzugefügt.",
        "en": "{count} terms added to the glossary.",
    },
    "ai.glossary.addedOne": {
        "de": "1 Begriff zum Glossar hinzugefügt.",
        "en": "1 term added to the glossary.",
    },
    # Maintenance mode
    "maintenance.message": {
        "de": "Wartungsarbeiten - bitte später erneut versuchen.",
        "en": "Maintenance in progress - please try again later.",
    },
    # Tool labels (shown in job listing)
    "tool.screencast_render": {"de": "Screencast", "en": "Screencast"},
    "tool.screencast_translate": {"de": "Screencast", "en": "Screencast"},
    "tool.tts": {"de": "Text in Audio", "en": "Text to audio"},
    "tool.translation": {"de": "Übersetzung", "en": "Translation"},
    "tool.transcription": {"de": "Transkription", "en": "Transcription"},
    "tool.image_generate": {"de": "Bild-Generierung", "en": "Image generation"},
    "tool.image_edit": {"de": "Bild-Bearbeitung", "en": "Image editing"},
    "tool.image_analyze": {"de": "Bild-Analyse", "en": "Image analysis"},
    "tool.summary": {"de": "Report", "en": "Report"},
    "tool.podcast": {"de": "Podcast", "en": "Podcast"},
    # Translate provider labels
    "translateProvider.deepl": {"de": "DeepL (schnell)", "en": "DeepL (fast)"},
    "translateProvider.llm": {"de": "LLM (langsam)", "en": "LLM (slow)"},
    # Translate language labels (DeepL codes)
    "lang.DE": {"de": "Deutsch", "en": "German"},
    "lang.EN-US": {"de": "Englisch", "en": "English"},
    "lang.FR": {"de": "Französisch", "en": "French"},
    "lang.ES": {"de": "Spanisch", "en": "Spanish"},
    "lang.IT": {"de": "Italienisch", "en": "Italian"},
    "lang.TR": {"de": "Türkisch", "en": "Turkish"},
    "lang.AR": {"de": "Arabisch", "en": "Arabic"},
    "lang.RU": {"de": "Russisch", "en": "Russian"},
}


def parse_accept_language(header: str | None) -> str:
    """Return the first supported locale from Accept-Language, or DEFAULT_LOCALE."""
    if not header:
        return DEFAULT_LOCALE
    for raw in header.split(","):
        tag = raw.strip().split(";")[0].lower()
        primary = tag.split("-")[0]
        if primary in SUPPORTED_LOCALES:
            return primary
    return DEFAULT_LOCALE


async def get_locale(
    accept_language: str | None = Header(default=None),
    lang: str | None = Query(default=None),
) -> str:
    """FastAPI dependency: resolve user locale from `?lang=` or Accept-Language."""
    if lang and lang in SUPPORTED_LOCALES:
        return lang
    return parse_accept_language(accept_language)


def register_messages(extra: dict[str, dict[str, str]]) -> None:
    """Backfills further translations from a submodule."""
    MESSAGES.update(extra)


def t(key: str, locale: str = DEFAULT_LOCALE, **params: object) -> str:
    """Translate a message key. Falls back to default locale, then to the key itself."""
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(locale) or entry.get(DEFAULT_LOCALE) or key
    return text.format(**params) if params else text


# Backfills the submodules, imported late against cycles.
def _load_fragments() -> None:
    try:
        from src._i18n_fragments import (  # noqa: F401
            access_codes,
            admin,
            ai_assistant,
            campus,
            consent,
            evaluation,
            event,
            feedback,
            impersonation,
            invites,
            jobs,
            own_interfaces,
            pages,
            praesentation,
            screencast,
        )

        for module in (
            ai_assistant, jobs, admin, invites, access_codes, impersonation, feedback, evaluation, praesentation,
            screencast, own_interfaces, event, campus, pages, consent,
        ):
            entries = getattr(module, "MESSAGES", None)
            if entries:
                register_messages(entries)
    except ImportError:
        pass


_load_fragments()
