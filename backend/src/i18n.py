"""i18n helper for backend user-facing strings.

Locale is resolved from Accept-Language (or an explicit `?lang=` query param).
Use `get_locale` as a FastAPI dependency, then pass the result to `t()`:

    from src.i18n import get_locale, t

    @router.get("/foo")
    async def foo(locale: str = Depends(get_locale)):
        raise HTTPException(401, t("auth.notAuthenticated", locale))

For Celery workers and other contexts without HTTP access, pass the locale
explicitly (e.g. from a `creator_locale` column on the job).
"""

from fastapi import Header, Query

SUPPORTED_LOCALES = ("de", "en")
DEFAULT_LOCALE = "de"


# All user-facing backend strings live here. Keys follow `area.key` convention.
# Add to BOTH locales when introducing a new key.
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
    # Common errors (broadly reused across feature routes)
    "workspace.notFound": {"de": "Modul nicht gefunden", "en": "Workspace not found"},
    "workspace.accessDenied": {"de": "Kein Zugriff", "en": "Access denied"},
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
        "de": "Zeitlimit überschritten. Bitte 'Wiederholen' klicken.",
        "en": "Time limit exceeded. Please click 'Retry'.",
    },
    "job.providerUnreachableRetry": {
        "de": "{provider} war ~90 Minuten nicht erreichbar. Bitte 'Wiederholen' klicken wenn der Dienst wieder verfügbar ist.",
        "en": "{provider} was unreachable for ~90 minutes. Please click 'Retry' once the service is back.",
    },
    "job.watchdogStuck": {
        "de": "Job hat sich nicht mehr gemeldet (möglicher Absturz oder Hänger). Bitte Wiederholen klicken.",
        "en": "Job stopped reporting progress (possible crash or hang). Please click 'Retry'.",
    },
    "job.watchdogStaleAwaiting": {
        "de": "Job abgelaufen (keine Eingabe erfolgt). Bitte neuen Screencast starten.",
        "en": "Job expired (no input received). Please start a new screencast.",
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
    # Quota labels (interpolated into quota.limitReached)
    "quota.label.tts": {"de": "Text in Sprache", "en": "Text to speech"},
    "quota.label.summary": {"de": "Zusammenfassung", "en": "Summary"},
    "quota.label.translate": {"de": "Dokumentenübersetzung", "en": "Document translation"},
    "quota.label.transcription": {"de": "Transkription", "en": "Transcription"},
    "quota.label.image_generate": {"de": "Bild-Generierung", "en": "Image generation"},
    "quota.label.image_edit": {"de": "Bild-Bearbeitung", "en": "Image editing"},
    "quota.label.image_analyze": {"de": "Bild-Analyse", "en": "Image analysis"},
    "quota.label.screencast": {"de": "Screencast", "en": "Screencast"},
    "quota.label.aia_generate": {"de": "KI-Tutor: Generierung", "en": "AI tutor: generation"},
    "source.notFound": {"de": "Source nicht gefunden", "en": "Source not found"},
    "entry.notFound": {"de": "Eintrag nicht gefunden", "en": "Entry not found"},
    "set.notFound": {"de": "Set nicht gefunden", "en": "Set not found"},
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
    "translate.invalidProvider": {
        "de": "Ungültiger Übersetzungs-Provider",
        "en": "Invalid translation provider",
    },
    "glossary.notProvided": {
        "de": "Kein Glossary vorhanden",
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
    "elevenlabs.notConfigured": {
        "de": "ElevenLabs API Key nicht konfiguriert",
        "en": "ElevenLabs API key not configured",
    },
    "kokoro.unreachable": {
        "de": "Kokoro Server nicht erreichbar",
        "en": "Kokoro server unreachable",
    },
    "mylab.ttsUnreachable": {
        "de": "myLab TTS Server nicht erreichbar",
        "en": "myLab TTS server unreachable",
    },
    # Rate limiting / burst block
    "rateLimit.blocked": {
        "de": "Chat ist bis {time} Uhr gesperrt (zu viele Anfragen in kurzer Zeit). Bitte später erneut versuchen.",
        "en": "Chat is locked until {time} (too many requests in a short time). Please try again later.",
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
        "de": "Glossary voll ({current} / {max}) - entferne Begriffe um neue hinzuzufügen.",
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
        "de": "Die erkannten Begriffe sind bereits im Glossary.",
        "en": "The detected terms are already in the glossary.",
    },
    "ai.glossary.noNewTerms": {
        "de": "Keine neuen lernenswerten Begriffe in der Markierung gefunden.",
        "en": "No new worthwhile terms found in the selection.",
    },
    "ai.glossary.added": {
        "de": "{count} Begriffe zum Glossary hinzugefügt.",
        "en": "{count} terms added to the glossary.",
    },
    # Maintenance mode
    "maintenance.message": {
        "de": "Wartungsarbeiten - bitte später erneut versuchen.",
        "en": "Maintenance in progress - please try again later.",
    },
    # Tool labels (shown in job listing)
    "tool.screencast_demo_render": {"de": "Demo-Screencast", "en": "Demo screencast"},
    "tool.screencast_render": {"de": "Screencast", "en": "Screencast"},
    "tool.screencast_translate": {
        "de": "Screencast-Übersetzung",
        "en": "Screencast translation",
    },
    "tool.tts": {"de": "Text in Sprache", "en": "Text to speech"},
    "tool.translation": {"de": "Übersetzung", "en": "Translation"},
    "tool.transcription": {"de": "Transkription", "en": "Transcription"},
    "tool.image_generate": {"de": "Bild-Generierung", "en": "Image generation"},
    "tool.image_edit": {"de": "Bild-Bearbeitung", "en": "Image editing"},
    "tool.image_analyze": {"de": "Bild-Analyse", "en": "Image analysis"},
    "tool.summary": {"de": "Zusammenfassung", "en": "Summary"},
    # Translate provider labels
    "translateProvider.deepl": {"de": "DeepL (schnell)", "en": "DeepL (fast)"},
    "translateProvider.llm": {"de": "LLM (langsam)", "en": "LLM (slow)"},
    # Translate language labels (DeepL codes)
    "lang.DE": {"de": "Deutsch", "en": "German"},
    "lang.EN-US": {"de": "Englisch", "en": "English"},
    "lang.EN-GB": {"de": "Englisch (UK)", "en": "English (UK)"},
    "lang.FR": {"de": "Französisch", "en": "French"},
    "lang.ES": {"de": "Spanisch", "en": "Spanish"},
    "lang.IT": {"de": "Italienisch", "en": "Italian"},
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
    """Register additional translation entries from a sub-module.

    Used by feature-specific message fragments (see `src/_i18n_fragments/`)
    to keep niche keys close to their feature without bloating this file.
    """
    MESSAGES.update(extra)


def t(key: str, locale: str = DEFAULT_LOCALE, **params: object) -> str:
    """Translate a message key. Falls back to default locale, then to the key itself."""
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(locale) or entry.get(DEFAULT_LOCALE) or key
    return text.format(**params) if params else text


# Register feature-specific message fragments. Imported lazily to avoid
# circular imports if a fragment ever needs `t()` itself.
def _load_fragments() -> None:
    try:
        from src._i18n_fragments import ai_assistant, jobs, admin  # noqa: F401

        for module in (ai_assistant, jobs, admin):
            entries = getattr(module, "MESSAGES", None)
            if entries:
                register_messages(entries)
    except ImportError:
        pass


_load_fragments()
