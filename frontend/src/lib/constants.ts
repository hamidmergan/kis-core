/** Max upload size for general documents (translate, summary, image). */
export const MAX_UPLOAD_MB = 500;
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

/** Max upload size for audio/video transcription. */
export const MAX_TRANSCRIPTION_MB = 500;
export const MAX_TRANSCRIPTION_BYTES = MAX_TRANSCRIPTION_MB * 1024 * 1024;

/** Longest playing time for transcription, checked in the browser instead of after the upload. */
export const MAX_TRANSCRIPTION_MINUTES = 100;

/** Max upload size for images (image edit/analyze). */
export const MAX_IMAGE_MB = 20;
export const MAX_IMAGE_BYTES = MAX_IMAGE_MB * 1024 * 1024;

/** Max script chars for screencast (mirrors backend SCREENCAST_MAX_CHARS in limits.py). */
export const SCREENCAST_MAX_CHARS = 100_000;

/** Max chars for direct text-to-speech input (mirrors backend TTS_MAX_CHARS in limits.py). */
export const TTS_MAX_CHARS = 100_000;

/** Max chars for direct translate text input (mirrors backend TRANSLATE_MAX_CHARS in limits.py). */
export const TRANSLATE_MAX_CHARS = 100_000;

/** UI locales for the header language switch (next-intl). */
export const UI_LOCALES = ["de", "en"] as const;
export const DEFAULT_UI_LOCALE: (typeof UI_LOCALES)[number] = "de";

/** Translate-tool language codes (DeepL format). Mirrors backend TRANSLATE_LANGUAGES in i18n.py. */
export const TRANSLATE_LANGUAGES = ["DE", "EN-US", "FR", "ES", "IT", "TR", "AR", "RU"] as const;
export const DEFAULT_TRANSLATE_TARGET: (typeof TRANSLATE_LANGUAGES)[number] = "EN-US";
/** Screencast: only these languages the voice speaks cleanly, measured at the provider. */
export const SCREENCAST_TARGET_LANGUAGES = ["DE", "EN-US"] as const;

/** LocalStorage key + custom event so the header settings menu can re-show a dismissed HomeNotice. */
export const HOME_NOTICE_DISMISS_KEY = "kis.home-notice.dismissed-text";
export const HOME_NOTICE_SHOW_EVENT = "kis:home-notice-show";

/** LocalStorage key prefix for the first-login welcome dialog, suffixed with the user id so a shared browser tracks each account separately. */
export const WELCOME_MODAL_SEEN_KEY_PREFIX = "kis.welcome-modal.seen.";
