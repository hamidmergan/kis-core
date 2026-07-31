"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import type { AccessLink } from "../_shared";

interface AddLinkModalProps {
  workspaceUuid: string;
  onClose: () => void;
  onCreated: (link: AccessLink) => void;
}

export default function AddLinkModal({ workspaceUuid, onClose, onCreated }: AddLinkModalProps) {
  const t = useTranslations("workspace.list");
  const [expiresAt, setExpiresAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/access-links`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        // Empty means the link never expires. Not every course has an end date.
        body: JSON.stringify({ expires_at: expiresAt ? new Date(expiresAt).toISOString() : null }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? t("createError"));
      }
      const data = await res.json();
      onCreated(data);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("unknownError"));
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
        <h2 className="text-lg font-semibold mb-2">{t("newLinkTitle")}</h2>
        <p className="text-sm mb-4" style={{ color: "var(--muted)" }}>
          {t("newLinkBody")}
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--foreground)" }}>
              {t("validUntilOptionalField")}
            </label>
            <input
              type="date"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              min={new Date().toISOString().split("T")[0]}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none"
              style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--foreground)" }}
            />
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
              {t("validUntilHint")}
            </p>
          </div>
          {error && (
            <p className="text-sm" style={{ color: "var(--error)" }}>
              {error}
            </p>
          )}
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="btn-cancel px-4 py-2 rounded-lg text-sm font-medium"
              style={{ backgroundColor: "var(--border)", color: "var(--foreground)" }}
            >
              {t("cancel")}
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            >
              {loading ? t("creating") : t("create")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
