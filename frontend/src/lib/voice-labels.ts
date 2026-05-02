export const KOKORO_ACCENT_LABEL: Record<string, string> = {
  "American": "🇺🇸",
  "British": "🇬🇧",
};

/**
 * Translate a comma-separated voice description into the active locale.
 * Pass a translator from `useTranslations("tools.tts.voiceDescription")` so
 * this stays a pure helper without React-context dependencies.
 */
export function translateVoiceDescription(
  description: string | null | undefined,
  t: (key: string) => string,
): string | null {
  if (!description) return null;
  return description
    .split(",")
    .map((d) => {
      const key = d.trim();
      try {
        return t(key);
      } catch {
        return key;
      }
    })
    .join(" · ");
}

/** @deprecated Use translateVoiceDescription with a translator instead. */
export function translateDesc(description?: string | null): string | null {
  if (!description) return null;
  return description
    .split(",")
    .map((d) => d.trim())
    .join(" · ");
}
