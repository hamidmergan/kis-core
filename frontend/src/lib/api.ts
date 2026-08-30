const API_BASE = "";
const BACKEND_BASE = "/api";

/** The backend sends exactly this detail when a test access has run out. */
const ACCESS_EXPIRED_DETAIL = "access_expired";
const EXPIRED_PATH = "/redeem/expired";

const FALLBACKS = {
  de: {
    limitReached: "Limit erreicht",
    unknownError: "Unbekannter Fehler",
    translationError: "Übersetzungsfehler",
    jobStatusError: "Fehler beim Abrufen des Job-Status",
    // Shown whenever the backend gives no usable detail - never the raw status code.
    genericError: "Da ist etwas schiefgelaufen. Bitte versuche es erneut oder wende dich an den Support, falls es weiter nicht klappt.",
    jobFailed: "Job fehlgeschlagen",
    downloadFailed: "Download fehlgeschlagen",
  },
  en: {
    limitReached: "Limit reached",
    unknownError: "Unknown error",
    translationError: "Translation error",
    jobStatusError: "Failed to load job status",
    genericError: "Something went wrong. Please try again, or contact support if it keeps happening.",
    jobFailed: "Job failed",
    downloadFailed: "Download failed",
  },
} as const;

function fallback(key: keyof typeof FALLBACKS["de"]): string {
  return FALLBACKS[readLocaleFromCookie()][key];
}

/** Locale-aware fallback text for spots outside ApiClient that need one, never the raw status code. */
export function genericErrorMessage(): string {
  return fallback("genericError");
}

export class QuotaError extends Error {
  quota_type: string;
  label: string;
  reset_at: string | null;
  used: number;
  limit: number;

  constructor(detail: Record<string, unknown>) {
    super(typeof detail.message === "string" ? detail.message : fallback("limitReached"));
    this.name = "QuotaError";
    this.quota_type = String(detail.quota_type ?? "");
    this.label = String(detail.label ?? detail.quota_type ?? "");
    this.reset_at = (detail.reset_at as string | null) ?? null;
    this.used = Number(detail.used ?? 0);
    this.limit = Number(detail.limit ?? 0);
  }
}

export function parseDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in (detail as object)) {
    return String((detail as Record<string, unknown>).message);
  }
  return fallback;
}

// Takes the file name from the header, otherwise the fallback.
export function filenameFromDisposition(disposition: string | null, fallback: string): string {
  if (disposition) {
    const utf8Match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/i);
    if (utf8Match) return decodeURIComponent(utf8Match[1].trim());
    const basicMatch = disposition.match(/filename="?([^";\n]+)"?/i);
    if (basicMatch) return decodeURIComponent(basicMatch[1].trim());
  }
  return fallback;
}

function _parseErrorResponse(errorBody: { detail?: unknown }, fallbackStatus: number): Error {
  const detail = errorBody.detail;
  if (detail && typeof detail === "object" && "quota_type" in (detail as object)) {
    return new QuotaError(detail as Record<string, unknown>);
  }
  // Blocks carry their sentence in detail.message, otherwise only 429 would show.
  if (detail && typeof detail === "object" && "message" in (detail as object)) {
    return new Error(String((detail as Record<string, unknown>).message));
  }
  if (typeof detail === "string") return new Error(detail);
  // Validation errors and bodies without a usable detail land here - log the status for debugging,
  // but never put the raw code in front of the user.
  console.error(`API error ${fallbackStatus}:`, detail);
  return new Error(fallback("genericError"));
}

function readLocaleFromCookie(): "de" | "en" {
  if (typeof document === "undefined") return "de";
  const match = document.cookie.match(/(?:^|;\s*)NEXT_LOCALE=(de|en)/);
  return (match?.[1] as "de" | "en") ?? "de";
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async fetch(path: string, options: RequestInit = {}): Promise<Response> {
    const headers = new Headers(options.headers);
    if (!headers.has("Accept-Language")) {
      headers.set("Accept-Language", readLocaleFromCookie());
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      credentials: "include",
      headers,
    });

    if (response.status === 401 && typeof window !== "undefined") {
      const currentPath = window.location.pathname;
      if (currentPath !== "/login") {
        window.location.href = "/login";
      }
    }

    // Only the expired test access redirects, every other 403 stays a plain error.
    if (response.status === 403 && typeof window !== "undefined") {
      const detail = await response
        .clone()
        .json()
        .then((body) => (body as { detail?: unknown })?.detail)
        .catch(() => null);
      if (detail === ACCESS_EXPIRED_DETAIL) {
        const currentPath = window.location.pathname;
        if (currentPath !== EXPIRED_PATH) {
          window.location.href = EXPIRED_PATH;
        }
      }
    }

    return response;
  }

  async postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
    const response = await this.fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: fallback("unknownError") }));
      throw _parseErrorResponse(error, response.status);
    }

    return response.json();
  }

  async getJson<T>(path: string): Promise<T> {
    const response = await this.fetch(path);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: fallback("unknownError") }));
      throw _parseErrorResponse(error, response.status);
    }

    return response.json();
  }

  async patchJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
    const response = await this.fetch(path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: fallback("unknownError") }));
      throw _parseErrorResponse(error, response.status);
    }

    return response.json();
  }

  async uploadFileWithFields(
    path: string,
    file: File,
    fields: Record<string, string>,
    fileFieldName: string = "file",
    signal?: AbortSignal,
  ): Promise<{ blob: Blob; filename: string }> {
    const formData = new FormData();
    formData.append(fileFieldName, file);
    for (const [key, value] of Object.entries(fields)) {
      formData.append(key, value);
    }

    const response = await this.fetch(path, {
      method: "POST",
      body: formData,
      signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: fallback("unknownError") }));
      throw _parseErrorResponse(error, response.status);
    }

    const blob = await response.blob();
    const filename = filenameFromDisposition(response.headers.get("Content-Disposition"), file.name);

    return { blob, filename };
  }

  async uploadFile(
    path: string,
    file: File,
    glossary?: Record<string, string>,
  ): Promise<{ blob: Blob; filename: string }> {
    const formData = new FormData();
    formData.append("file", file);
    if (glossary && Object.keys(glossary).length > 0) {
      formData.append("glossary", JSON.stringify(glossary));
    }

    const response = await this.fetch(path, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: fallback("translationError") }));
      throw _parseErrorResponse(error, response.status);
    }

    const blob = await response.blob();
    const filename = filenameFromDisposition(response.headers.get("Content-Disposition"), file.name);

    return { blob, filename };
  }
  async postJsonForBlob(
    path: string,
    body: unknown,
  ): Promise<{ blob: Blob; filename: string }> {
    const response = await this.fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: fallback("unknownError") }));
      throw _parseErrorResponse(error, response.status);
    }

    const blob = await response.blob();
    const filename = filenameFromDisposition(response.headers.get("Content-Disposition"), "output");

    return { blob, filename };
  }

  async uploadMultipleFiles(
    path: string,
    files: Record<string, File>,
    fields: Record<string, string> = {},
  ): Promise<{ blob: Blob; filename: string }> {
    const formData = new FormData();
    for (const [key, file] of Object.entries(files)) {
      formData.append(key, file);
    }
    for (const [key, value] of Object.entries(fields)) {
      formData.append(key, value);
    }

    const response = await this.fetch(path, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: fallback("unknownError") }));
      throw _parseErrorResponse(error, response.status);
    }

    const blob = await response.blob();
    const filename = filenameFromDisposition(response.headers.get("Content-Disposition"), "output");

    return { blob, filename };
  }
}

export const api = new ApiClient(API_BASE);
export const backendApi = new ApiClient(BACKEND_BASE);

// ── Job polling helpers ────────────────────────────────────────────────────

export interface JobStatus {
  job_uuid: string;
  status: "pending" | "running" | "success" | "failed" | "awaiting_user";
  tool: string;
  original_filename: string;
  progress: Record<string, unknown> | null;
  error: string | null;
  download_url: string | null;
  result: Record<string, unknown> | null;
  meta: Record<string, unknown> | null;
}

/** Polls a job to the end and reports every progress update. */
export async function pollJob(
  jobUuid: string,
  onProgress?: (status: JobStatus) => void,
  intervalMs = 3000,
  signal?: AbortSignal,
  onStuck?: () => void,
  stuckThresholdMs = 30_000,
): Promise<JobStatus> {
  let lastProgressJson = "";
  let lastProgressChangeAt = Date.now();

  while (true) {
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

    const res = await fetch(`/api/jobs/${jobUuid}`, { credentials: "include", signal });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      if (!body) {
        console.error(`Job status fetch failed with ${res.status}`);
        throw new Error(fallback("jobStatusError"));
      }
      throw _parseErrorResponse(body, res.status);
    }

    const status: JobStatus = await res.json();

    // Track progress changes for stuck detection
    const currentProgressJson = JSON.stringify(status.progress);
    if (currentProgressJson !== lastProgressJson) {
      lastProgressJson = currentProgressJson;
      lastProgressChangeAt = Date.now();
    } else if ((status.status === "running" || status.status === "pending") && onStuck && Date.now() - lastProgressChangeAt > stuckThresholdMs) {
      onStuck();
    }

    onProgress?.(status);

    if (status.status === "success") return status;
    if (status.status === "awaiting_user") return status;
    if (status.status === "failed") throw new Error(status.error || fallback("jobFailed"));

    await new Promise<void>((resolve, reject) => {
      let timer: ReturnType<typeof setTimeout>;
      const onAbort = () => { clearTimeout(timer); reject(new DOMException("Aborted", "AbortError")); };
      // Detach on the normal path too, otherwise every round adds a listener.
      timer = setTimeout(() => { signal?.removeEventListener("abort", onAbort); resolve(); }, intervalMs);
      signal?.addEventListener("abort", onAbort, { once: true });
    });
  }
}

/** Downloads the result file of a finished job. */
export async function downloadJobAsBlob(
  jobUuid: string,
  fallbackFilename = "output",
): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`/api/jobs/${jobUuid}/download`, { credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    if (!body) {
      console.error(`Job download failed with ${res.status}`);
      throw new Error(fallback("downloadFailed"));
    }
    throw _parseErrorResponse(body, res.status);
  }

  const blob = await res.blob();
  const filename = filenameFromDisposition(res.headers.get("Content-Disposition"), fallbackFilename);
  return { blob, filename };
}
