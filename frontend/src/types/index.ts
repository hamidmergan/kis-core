export interface AuthStatus {
  authenticated: boolean;
  user_id?: number;
  username?: string;
  display_name?: string;
  email?: string;
  is_admin?: boolean;
}

export interface LoginResponse {
  status: string;
  username: string;
  display_name: string;
}

export interface ApiError {
  detail: string;
}

export type TranslationState = "idle" | "uploading" | "translating" | "done" | "error";

export type TTSState = "idle" | "uploading" | "processing" | "done" | "error";

export type ScriptState = "idle" | "uploading" | "processing" | "done" | "error";

export type TranscriptionState = "idle" | "uploading" | "processing" | "done" | "error";

export type VideoDubbingState = "idle" | "uploading" | "processing" | "done" | "error";

export type ScreencastState = "idle" | "uploading" | "processing" | "done" | "error";

export type SummaryState = "idle" | "processing" | "done" | "error";

export type ScreencastMode = "auto" | "manual";

export type ScreencastStep =
  | "upload"
  | "translating"
  | "user-prompt"
  | "translation-review"
  | "preparing"
  | "generating-scripts"
  | "script-review"
  | "tts-settings"
  | "rendering"
  | "done"
  | "error";

export interface GlossaryEntry {
  source: string;
  target: string;
}

export interface Glossary {
  id: string;
  name: string;
  entries: Record<string, string>;
  createdAt: string;
}

export interface SlideData {
  index: number;
  imageBase64: string;
  extractedText: string;
  script: string;
}
