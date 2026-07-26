"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

/**
 * The adaptive answer behaviour that steers the existing workspace chat.
 *
 * For a learner with a stored CEFR level, this text (with `{level}` replaced by
 * the level) is appended to the chat system prompt. Saving an empty field
 * restores the shipped default, so the behaviour is never left blank.
 */
export default function DiagnosisAdaptiveBehaviorCard() {
  const t = useTranslations("admin.adaptiveBehaviorCard");
  const [saved, setSaved] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [fallback, setFallback] = useState("");
  const [windowDays, setWindowDays] = useState<number>(30);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const value = typeof d.language_diagnosis_adaptive_behavior === "string"
          ? d.language_diagnosis_adaptive_behavior : "";
        setSaved(value);
        setDraft(value);
        setFallback(
          typeof d.language_diagnosis_adaptive_behavior_default === "string"
            ? d.language_diagnosis_adaptive_behavior_default : "",
        );
        if (typeof d.learner_profile_window_days === "number") {
          setWindowDays(d.learner_profile_window_days);
        }
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
        body: JSON.stringify({ language_diagnosis_adaptive_behavior: value }),
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
      const stored = value.trim() || fallback;
      setSaved(stored);
      setDraft(stored);
    } finally {
      setSaving(false);
    }
  };

  const commitWindowDays = async (days: number) => {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ learner_profile_window_days: days }),
      });
      if (!res.ok) {
        let detail = t("saveFailed");
        try {
          const body = await res.json();
          if (typeof body?.detail === "string") detail = body.detail;
        } catch { /* ignore */ }
        setError(detail);
      }
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
        rows={8}
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
      <div className="mt-4 pt-4 border-t border-border-soft">
        <label className="text-xs text-muted">{t("windowDaysLabel")}</label>
        <input
          type="number" min={1} max={3650} value={windowDays}
          onChange={(e) => setWindowDays(Number(e.target.value))}
          onBlur={() => void commitWindowDays(windowDays)}
          disabled={saving}
          className="ml-2 w-24 rounded-lg border border-border bg-background px-2 py-1 text-xs text-foreground"
        />
        <p className="text-xs text-muted-soft mt-1">{t("windowDaysHint")}</p>
      </div>
      {error && (
        <p className="mt-2 text-xs text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2">
          {error}
        </p>
      )}
    </div>
  );
}
