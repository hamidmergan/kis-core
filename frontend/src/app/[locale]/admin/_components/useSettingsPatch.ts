import { useState } from "react";

/** Saves admin settings and keeps the saving flag and the error text. */
export function useSettingsPatch(fallbackError: string) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Resolves to true when the server took the values. */
  const patch = async (payload: Record<string, unknown>): Promise<boolean> => {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        let detail = fallbackError;
        try {
          const body = await res.json();
          if (typeof body?.detail === "string") detail = body.detail;
        } catch { /* ignore */ }
        setError(detail);
      }
      return res.ok;
    } catch {
      setError(fallbackError);
      return false;
    } finally {
      setSaving(false);
    }
  };

  return { saving, error, setError, patch };
}
