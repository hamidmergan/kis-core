export const KOKORO_LANGUAGE_ORDER = ["English"];
export const KOKORO_LANGUAGE_LABEL: Record<string, string> = {
  "English": "🇺🇸🇬🇧 English",
};

export const MYLAB_LANGUAGE_ORDER = ["de", "en"];
export const MYLAB_LANGUAGE_LABEL: Record<string, string> = {
  "de": "🇩🇪 Deutsch",
  "en": "🇺🇸 English",
};


export interface KokoroVoice {
  voice_id: string;
  name: string;
  language?: string;
  accent: string;
  gender: string;
}

export interface OpenAITtsVoice {
  voice_id: string;
  name: string;
  description: string;
  language?: string;
}

export type VoicesTab = "kokoro" | "mylab";
