"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

/**
 * The system prompt behind the CEFR chat diagnosis.
 *
 * One prompt covers every language: `{language}` is replaced with the workspace's
 * diagnosis language at request time. Saving an empty field restores the shipped
 * default, so the diagnosis can never end up without instructions.
 */
export default function LanguageDiagnosisCard() {
  const t = useTranslations("admin.languageDiagnosisCard");
  const [saved, setSaved] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [fallback, setFallback] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const value = typeof d.language_diagnosis_prompt === "string" ? d.language_diagnosis_prompt : "";
        setSaved(value);
        setDraft(value);
        setFallback(
          typeof d.language_diagnosis_prompt_default === "string"
            ? d.language_diagnosis_prompt_default
            : "",
        );
      })
      .catch(() => setSaved(""));
  }, []);

  const commit = async (value: string) => {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language_diagnosis_prompt: value }),
      });
      if (!res.ok) {
        let detail = t("saveFailed");
        try {
          const body = await res.json();
          if (typeof body?.detail === "string") detail = body.detail;
          else if (body?.detail?.message) detail = body.detail.message;
        } catch { /* ignore */ }
        setError(detail);
        setDraft(saved ?? "");
        return;
      }
      // An empty save is the reset gesture: the backend stores the default, so
      // mirror that here instead of showing a blank prompt.
      const stored = value.trim() || fallback;
      setSaved(stored);
      setDraft(stored);
    } finally {
      setSaving(false);
    }
  };

  if (saved === null) return null;

  const isDefault = draft.trim() === fallback.trim();

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="text-sm font-medium text-foreground">{t("title")}</p>
      <p className="text-xs text-muted mt-1">{t("description")}</p>
      <textarea
        value={draft}
        onChange={(e) => { setDraft(e.target.value); setError(null); }}
        onBlur={() => { if (draft !== saved) void commit(draft); }}
        disabled={saving}
        rows={14}
        className="mt-3 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs font-mono text-foreground focus:outline-none focus:border-kb disabled:opacity-50 resize-y"
      />
      <div className="mt-2 flex items-center justify-between gap-3">
        <p className="text-xs text-muted-soft">{t("hint")}</p>
        <button
          type="button"
          onClick={() => void commit("")}
          disabled={saving || isDefault}
          className="shrink-0 text-xs px-3 py-1.5 rounded-lg border border-border text-foreground enabled:hover:border-kb disabled:opacity-40"
        >
          {t("reset")}
        </button>
      </div>
      {error && (
        <p className="mt-2 text-xs text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2">
          {error}
        </p>
      )}
    </div>
  );
}
