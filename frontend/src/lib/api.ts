const API_BASE = "";
const BACKEND_BASE = "http://localhost:8000";

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

  async postJson<T>(path: string, body: unknown): Promise<T> {
    const response = await this.fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
      throw new Error(error.detail || `Fehler: ${response.status}`);
    }

    return response.json();
  }

  async getJson<T>(path: string): Promise<T> {
    const response = await this.fetch(path);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
      throw new Error(error.detail || `Fehler: ${response.status}`);
    }

    return response.json();
  }

  async uploadFileWithFields(
    path: string,
    file: File,
    fields: Record<string, string>,
    fileFieldName: string = "file",
  ): Promise<{ blob: Blob; filename: string }> {
    const formData = new FormData();
    formData.append(fileFieldName, file);
    for (const [key, value] of Object.entries(fields)) {
      formData.append(key, value);
    }

    const response = await this.fetch(path, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
      throw new Error(error.detail || `Fehler: ${response.status}`);
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
      throw new Error(error.detail || `Fehler: ${response.status}`);
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
      throw new Error(error.detail || `Fehler: ${response.status}`);
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
      throw new Error(error.detail || `Fehler: ${response.status}`);
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
