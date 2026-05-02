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
    # Provider configuration errors
    "llm.notConfigured": {
        "de": "Kein LLM-Provider konfiguriert",
        "en": "No LLM provider configured",
    },
    "elevenlabs.notConfigured": {
        "de": "ElevenLabs API Key nicht konfiguriert",
        "en": "ElevenLabs API key not configured",
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


def t(key: str, locale: str = DEFAULT_LOCALE, **params: object) -> str:
    """Translate a message key. Falls back to default locale, then to the key itself."""
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(locale) or entry.get(DEFAULT_LOCALE) or key
    return text.format(**params) if params else text
