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
