export const CATEGORY_DE: Record<string, string> = {
  professional: "Professionell",
  high_quality: "Hohe Qualität",
};

export const DESCRIPTION_DE: Record<string, string> = {
  "Laid-Back": "Entspannt",
  "Casual": "Locker",
  "Formal": "Förmlich",
  "Friendly": "Freundlich",
  "Warm": "Warm",
  "Authoritative": "Autoritär",
  "Confident": "Selbstsicher",
  "Calm": "Ruhig",
  "Energetic": "Energetisch",
  "Upbeat": "Lebhaft",
  "Serious": "Sachlich",
  "Raspy": "Rau",
  "Smooth": "Weich",
  "Deep": "Tief",
  "Resonant": "Resonant",
  "Crisp": "Klar",
  "Soft": "Sanft",
  "Husky": "Heiser",
  "Clear": "Deutlich",
  "Conversational": "Gesprächig",
  "Narrative": "Erzählend",
  "Expressive": "Ausdrucksstark",
  "Melodic": "Melodisch",
  "Mature": "Reif",
  "Powerful": "Kraftvoll",
  "Bright": "Hell",
  "Grounded": "Geerdet",
  "Soothing": "Beruhigend",
  "Professional": "Professionell",
};

export const USE_CASE_DE: Record<string, string> = {
  "narration": "Erzählung",
  "news": "Nachrichten",
  "audiobook": "Hörbuch",
  "conversational": "Gespräch",
  "conversation": "Gespräch",
  "social media": "Social Media",
  "social_media": "Social Media",
  "interactive": "Interaktiv",
  "video games": "Videospiele",
  "video_games": "Videospiele",
  "entertainment & tv": "Unterhaltung & TV",
  "entertainment_tv": "Unterhaltung & TV",
  "training & elearning": "Training & E-Learning",
  "training_elearning": "Training & E-Learning",
  "meditation": "Meditation",
  "characters": "Charaktere",
  "animation": "Animation",
  "characters_animation": "Charaktere & Animation",
  "narrative_story": "Erzählung",
  "informative_educational": "Bildung & Information",
  "advertisement": "Werbung",
  "ads": "Werbung",
};

export const KOKORO_LANGUAGE_ORDER = ["Deutsch", "English"];
export const KOKORO_LANGUAGE_LABEL: Record<string, string> = {
  "Deutsch": "🇩🇪 Deutsch",
  "English": "🇺🇸🇬🇧 English",
};

export function translateDesc(description?: string | null): string | null {
  if (!description) return null;
  return description.split(",").map(d => {
    const key = d.trim();
    return DESCRIPTION_DE[key] ?? key;
  }).join(" · ");
}

export function translateLabel(description?: string | null, use_case?: string | null): string | null {
  const parts: string[] = [];
  const desc = translateDesc(description);
  if (desc) parts.push(desc);
  if (use_case) parts.push(USE_CASE_DE[use_case.toLowerCase().trim()] ?? use_case);
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

export interface MylabVoice {
  voice_id: string;
  name: string;
  description: string;
}

export type VoicesTab = "elevenlabs" | "fish_speech" | "kokoro" | "mylab";
