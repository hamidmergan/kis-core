export const LANGUAGE_LABEL: Record<string, string> = {
  de: "🇩🇪 Deutsch",
  en: "🇺🇸 English",
  fr: "🇫🇷 Français",
  es: "🇪🇸 Español",
  it: "🇮🇹 Italiano",
  nl: "🇳🇱 Nederlands",
  pt: "🇵🇹 Português",
  pl: "🇵🇱 Polski",
  tr: "🇹🇷 Türkçe",
  zh: "🇨🇳 中文",
  ja: "🇯🇵 日本語",
  ko: "🇰🇷 한국어",
};

export interface ProviderWithVoices {
  id: number;
  name: string;
  voices: Voice[];
}

export interface Voice {
  voice_id: string;
  name: string;
  language: string;
  description?: string;
}
