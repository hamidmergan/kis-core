const API_BASE = "";
const BACKEND_BASE = "/api";

export class QuotaError extends Error {
  quota_type: string;
  label: string;
  reset_at: string | null;
  used: number;
  limit: number;

  constructor(detail: Record<string, unknown>) {
    super(typeof detail.message === "string" ? detail.message : "Limit erreicht");
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

function _parseErrorResponse(errorBody: { detail?: unknown }, fallbackStatus: number): Error {
  const detail = errorBody.detail;
  if (detail && typeof detail === "object" && "quota_type" in (detail as object)) {
    return new QuotaError(detail as Record<string, unknown>);
  }
  // Burst-Sperren (kind: "tool_blocked" | "chat_blocked") liefern die konkrete
  // Sperrnachricht in detail.message — sonst ginge sie als generisches "Fehler: 429" verloren.
  if (detail && typeof detail === "object" && "message" in (detail as object)) {
    return new Error(String((detail as Record<string, unknown>).message));
  }
  const msg = typeof detail === "string" ? detail : `Fehler: ${fallbackStatus}`;
  return new Error(msg);
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async fetch(path: string, options: RequestInit = {}): Promise<Response> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        ...options.headers,
      },
    });

    if (response.status === 401 && typeof window !== "undefined") {
      const currentPath = window.location.pathname;
      if (currentPath !== "/login") {
        window.location.href = "/login";
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
      const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
      throw _parseErrorResponse(error, response.status);
    }

    return response.json();
  }

  async getJson<T>(path: string): Promise<T> {
    const response = await this.fetch(path);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
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
      const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
      throw _parseErrorResponse(error, response.status);
    }

    const blob = await response.blob();
    let filename = "";

    const disposition = response.headers.get("Content-Disposition");
    if (disposition) {
      const utf8Match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/i);
      if (utf8Match) {
        filename = decodeURIComponent(utf8Match[1].trim());
      } else {
        const basicMatch = disposition.match(/filename="?([^";\n]+)"?/i);
        if (basicMatch) {
          filename = decodeURIComponent(basicMatch[1].trim());
        }
      }
    }

    if (!filename) {
      filename = file.name;
    }

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
      const error = await response.json().catch(() => ({ detail: "Übersetzungsfehler" }));
      throw _parseErrorResponse(error, response.status);
    }

    const blob = await response.blob();
    let filename = "";

    const disposition = response.headers.get("Content-Disposition");
    if (disposition) {
      // Try filename*=UTF-8'' first (RFC 5987)
      const utf8Match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/i);
      if (utf8Match) {
        filename = decodeURIComponent(utf8Match[1].trim());
      } else {
        // Fallback to filename="..."
        const basicMatch = disposition.match(/filename="?([^";\n]+)"?/i);
        if (basicMatch) {
          filename = decodeURIComponent(basicMatch[1].trim());
        }
      }
    }

    // Fallback: use original filename with English extension
    if (!filename) {
      filename = file.name;
    }

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
      const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
      throw _parseErrorResponse(error, response.status);
    }

    const blob = await response.blob();
    let filename = "";

    const disposition = response.headers.get("Content-Disposition");
    if (disposition) {
      const utf8Match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/i);
      if (utf8Match) {
        filename = decodeURIComponent(utf8Match[1].trim());
      } else {
        const basicMatch = disposition.match(/filename="?([^";\n]+)"?/i);
        if (basicMatch) {
          filename = decodeURIComponent(basicMatch[1].trim());
        }
      }
    }

    if (!filename) {
      filename = "output";
    }

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
      const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
      throw _parseErrorResponse(error, response.status);
    }

    const blob = await response.blob();
    let filename = "";

    const disposition = response.headers.get("Content-Disposition");
    if (disposition) {
      const utf8Match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/i);
      if (utf8Match) {
        filename = decodeURIComponent(utf8Match[1].trim());
      } else {
        const basicMatch = disposition.match(/filename="?([^";\n]+)"?/i);
        if (basicMatch) {
          filename = decodeURIComponent(basicMatch[1].trim());
        }
      }
    }

    if (!filename) {
      filename = "output";
    }

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

/**
 * Poll a job until it reaches a terminal state (success or failed).
 * Calls onProgress on every status update.
 * Throws on failure or if signal is aborted.
 */
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
    if (signal?.aborted) throw new DOMException("Abgebrochen", "AbortError");

    const res = await fetch(`/api/jobs/${jobUuid}`, { credentials: "include", signal });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Fehler beim Abrufen des Job-Status" }));
      throw new Error(err.detail || `Fehler: ${res.status}`);
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
    if (status.status === "failed") throw new Error(status.error || "Job fehlgeschlagen");

    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(resolve, intervalMs);
      signal?.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("Abgebrochen", "AbortError")); }, { once: true });
    });
  }
}

/**
 * Download the result file from a completed job as a Blob.
 */
export async function downloadJobAsBlob(
  jobUuid: string,
  fallbackFilename = "output",
): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`/api/jobs/${jobUuid}/download`, { credentials: "include" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Download fehlgeschlagen" }));
    throw new Error(err.detail || `Download-Fehler: ${res.status}`);
  }

  const blob = await res.blob();
  let filename = fallbackFilename;
  const disposition = res.headers.get("Content-Disposition");
  if (disposition) {
    const utf8Match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/i);
    if (utf8Match) {
      filename = decodeURIComponent(utf8Match[1].trim());
    } else {
      const basicMatch = disposition.match(/filename="?([^";\n]+)"?/i);
      if (basicMatch) filename = decodeURIComponent(basicMatch[1].trim());
    }
  }
  return { blob, filename };
}
