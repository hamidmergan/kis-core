"use client";

import { useState } from "react";
import type { AccessLink } from "../_shared";

interface AddLinkModalProps {
  moduleUuid: string;
  onClose: () => void;
  onCreated: (link: AccessLink) => void;
}

export default function AddLinkModal({ moduleUuid, onClose, onCreated }: AddLinkModalProps) {
  const [expiresAt, setExpiresAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!expiresAt) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/ki-assistent/modules/${moduleUuid}/access-links`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expires_at: new Date(expiresAt).toISOString() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Fehler beim Erstellen");
      }
      const data = await res.json();
      onCreated(data);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="w-full max-w-sm rounded-xl p-6 shadow-xl"
        style={{ backgroundColor: "var(--surface)" }}
      >
        <h2 className="text-lg font-semibold mb-2">Neuen Einschreibelink erstellen</h2>
        <p className="text-sm mb-4" style={{ color: "var(--muted)" }}>
          Jeder Link hat eine eigene Laufzeit. Studierende mit unterschiedlichen Links haben getrennte Chat-Verläufe.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
              Gültig bis
            </label>
            <input
              type="date"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              required
              min={new Date().toISOString().split("T")[0]}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none"
              style={{ backgroundColor: "var(--bg)", borderColor: "var(--border)", color: "var(--text)" }}
            />
          </div>
          {error && (
            <p className="text-sm" style={{ color: "#E11D48" }}>
              {error}
            </p>
          )}
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm font-medium"
              style={{ backgroundColor: "var(--border)", color: "var(--text)" }}
            >
              Abbrechen
            </button>
            <button
              type="submit"
              disabled={loading || !expiresAt}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 bg-primary"
            >
              {loading ? "Erstellen…" : "Erstellen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
