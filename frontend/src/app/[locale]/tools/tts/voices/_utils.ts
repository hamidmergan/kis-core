export const CATEGORY_KEYS = ["professional", "high_quality"] as const;

export const DESCRIPTION_KEYS = [
  "Laid-Back",
  "Casual",
  "Formal",
  "Friendly",
  "Warm",
  "Authoritative",
  "Confident",
  "Calm",
  "Energetic",
  "Upbeat",
  "Serious",
  "Raspy",
  "Smooth",
  "Deep",
  "Resonant",
  "Crisp",
  "Soft",
  "Husky",
  "Clear",
  "Conversational",
  "Narrative",
  "Expressive",
  "Melodic",
  "Mature",
  "Powerful",
  "Bright",
  "Grounded",
  "Soothing",
  "Professional",
] as const;

export const USE_CASE_KEYS = [
  "narration",
  "news",
  "audiobook",
  "conversational",
  "conversation",
  "social media",
  "social_media",
  "interactive",
  "video games",
  "video_games",
  "entertainment & tv",
  "entertainment_tv",
  "training & elearning",
  "training_elearning",
  "meditation",
  "characters",
  "animation",
  "characters_animation",
  "narrative_story",
  "informative_educational",
  "advertisement",
  "ads",
] as const;

export const KOKORO_LANGUAGE_ORDER = ["English"];
export const KOKORO_LANGUAGE_LABEL: Record<string, string> = {
  "English": "🇺🇸🇬🇧 English",
};

export const MYLAB_LANGUAGE_ORDER = ["de", "en"];
export const MYLAB_LANGUAGE_LABEL: Record<string, string> = {
  "de": "🇩🇪 Deutsch",
  "en": "🇺🇸 English",
};

export type DescriptionTranslator = (key: string) => string;
export type UseCaseTranslator = (key: string) => string;

export function translateDesc(
  description: string | null | undefined,
  tDesc: DescriptionTranslator,
): string | null {
  if (!description) return null;
  return description
    .split(",")
    .map((d) => {
      const key = d.trim();
      return (DESCRIPTION_KEYS as readonly string[]).includes(key) ? tDesc(key) : key;
    })
    .join(" · ");
}

export function translateLabel(
  description: string | null | undefined,
  use_case: string | null | undefined,
  tDesc: DescriptionTranslator,
  tUseCase: UseCaseTranslator,
): string | null {
  const parts: string[] = [];
  const desc = translateDesc(description, tDesc);
  if (desc) parts.push(desc);
  if (use_case) {
    const key = use_case.toLowerCase().trim();
    parts.push((USE_CASE_KEYS as readonly string[]).includes(key) ? tUseCase(key) : use_case);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}


export interface Voice {
  voice_id: string;
  label: string;
  preview_url: string | null;
  category?: string | null;
  description?: string | null;
  use_case?: string | null;
}

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

export type VoicesTab = "elevenlabs" | "kokoro" | "mylab";
