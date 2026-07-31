/** Max upload size for general documents (translate, summary, image). */
export const MAX_UPLOAD_MB = 500;
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

/** Max upload size for audio/video transcription. */
export const MAX_TRANSCRIPTION_MB = 500;
export const MAX_TRANSCRIPTION_BYTES = MAX_TRANSCRIPTION_MB * 1024 * 1024;

/**
 * Max playing time for transcription (mirrors backend MAX_AUDIO_SEC in
 * _chunking.py). Checked in the browser as well as on the server: the server
 * can only measure it after the whole file has been uploaded, so without the
 * browser check the user waits out a long upload just to be told no.
 */
export const MAX_TRANSCRIPTION_MINUTES = 100;

/** Max upload size for images (image edit/analyze). */
export const MAX_IMAGE_MB = 20;
export const MAX_IMAGE_BYTES = MAX_IMAGE_MB * 1024 * 1024;

/** Max script chars for screencast (mirrors backend SCREENCAST_MAX_CHARS in limits.py). */
export const SCREENCAST_MAX_CHARS = 100_000;

/** Max chars for direct text-to-speech input (mirrors backend TTS_MAX_CHARS in limits.py). */
export const TTS_MAX_CHARS = 100_000;

/** UI locales for the header language switch (next-intl). */
export const UI_LOCALES = ["de", "en"] as const;
export const DEFAULT_UI_LOCALE: (typeof UI_LOCALES)[number] = "de";
export type UiLocale = (typeof UI_LOCALES)[number];

/** Translate-tool language codes (DeepL format). Mirrors backend TRANSLATE_LANGUAGES in i18n.py. */
export const TRANSLATE_LANGUAGES = ["DE", "EN-US", "FR", "ES", "IT", "TR", "AR", "RU"] as const;
export const DEFAULT_TRANSLATE_TARGET: (typeof TRANSLATE_LANGUAGES)[number] = "EN-US";
export type TranslateLanguage = (typeof TRANSLATE_LANGUAGES)[number];

