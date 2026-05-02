"use client";

import { useState } from "react";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import type { KiTutorWorkspace } from "../_shared";

interface CreateWorkspaceModalProps {
  onClose: () => void;
  onCreated: (m: KiTutorWorkspace) => void;
}

export default function CreateWorkspaceModal({ onClose, onCreated }: CreateWorkspaceModalProps) {
  const labels = useWorkspaceLabel();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("title", title.trim());
      if (description.trim()) form.append("description", description.trim());
      if (expiresAt) form.append("expires_at", new Date(expiresAt).toISOString());
      const res = await fetch("/api/ai-assistant/workspaces", {
        method: "POST",
        credentials: "include",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Fehler beim Erstellen");
      }
      const created = await res.json();
      onCreated({
        uuid: created.uuid,
        title: title.trim(),
        description: description.trim() || null,
        status: "pending",
        source_count: 0,
        is_active: false,
        access_links: created.access_links ?? [],
        enroll_code: created.enroll_code ?? null,
        enroll_code_expires: created.enroll_code_expires ?? null,
        created_at: new Date().toISOString(),
      });
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
        className="w-full max-w-md rounded-xl p-4 sm:p-6 shadow-xl"
        style={{ backgroundColor: "var(--surface)" }}
      >
        <h2 className="text-lg font-semibold mb-5">{labels.singular} erstellen</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--foreground)" }}>
              Titel <span style={{ color: "var(--error)" }}>*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value.slice(0, 50))}
              required
              maxLength={50}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none"
              style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--foreground)" }}
              placeholder="z. B. Einführung in die Informatik"
            />
            <p className="text-xs text-muted-soft text-right mt-1">{title.length}/50</p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--foreground)" }}>
              Beschreibung
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value.slice(0, 300))}
              maxLength={300}
              rows={2}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none resize-none"
              style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--foreground)" }}
              placeholder="z. B. Sommersemester 2026, Grundlagen der Programmierung"
            />
            <p className="text-xs text-muted-soft text-right mt-1">{description.length}/300</p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--foreground)" }}>
              Einschreibelink gültig bis
            </label>
            <input
              type="date"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              min={new Date().toISOString().split("T")[0]}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none"
              style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--foreground)" }}
            />
          </div>
          {error && (
            <p className="text-sm" style={{ color: "var(--error)" }}>
              {error}
            </p>
          )}
          <div className="flex gap-3 justify-end mt-1">
            <button
              type="button"
              onClick={onClose}
              className="btn-cancel px-4 py-2 rounded-lg text-sm font-medium"
              style={{ backgroundColor: "var(--border)", color: "var(--foreground)" }}
            >
              Abbrechen
            </button>
            <button
              type="submit"
              disabled={loading || !title.trim()}
              className="btn-primary px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            >
              {loading ? "Erstellen…" : "Erstellen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
