export interface AuthStatus {
  authenticated: boolean;
}

export interface LoginResponse {
  status: string;
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

export interface SlideData {
  index: number;
  imageBase64: string;
  extractedText: string;
  script: string;
}
