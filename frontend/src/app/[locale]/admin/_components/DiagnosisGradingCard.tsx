"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import CollapsibleCard from "@/components/ui/CollapsibleCard";

/** The grading rules of the assessment, empty resets to the default. */
export default function DiagnosisGradingCard() {
  const t = useTranslations("admin.diagnosisGradingCard");
  const [rules, setRules] = useState<string | null>(null);
  const [savedRules, setSavedRules] = useState("");
  const [fallback, setFallback] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const value = typeof d.language_diagnosis_grading_rules === "string"
          ? d.language_diagnosis_grading_rules : "";
        setRules(value);
        setSavedRules(value);
        setFallback(
          typeof d.language_diagnosis_grading_rules_default === "string"
            ? d.language_diagnosis_grading_rules_default : "",
        );
      })
      .catch(() => setRules(""));
  }, []);

  const patch = async (payload: Record<string, unknown>) => {
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

  if (rules === null) return null;

  // Save only on a real change, otherwise just looking freezes the default.
  const commit = () => {
    if (rules === savedRules) return;
    setSavedRules(rules);
    void patch({ language_diagnosis_grading_rules: rules });
  };
  const reset = () => {
    setRules(fallback);
    setSavedRules(fallback);
    void patch({ language_diagnosis_grading_rules: "" });
  };

  const isDefault = rules.trim() === fallback.trim();

  return (
    <CollapsibleCard title={t("title")} description={t("description")}>
      <p className="mb-2 text-xs text-muted-soft">{t("hint")}</p>
      <textarea
        value={rules}
        onChange={(e) => { setRules(e.target.value); setError(null); }}
        onBlur={commit}
        disabled={saving}
        rows={9}
        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs font-mono text-foreground focus:outline-none focus:border-kb disabled:opacity-50 resize-y"
      />
      <div className="mt-2 flex justify-end">
        <button
          type="button"
          onClick={reset}
          disabled={saving || isDefault}
          className="text-xs px-3 py-1.5 rounded-lg border border-border text-foreground enabled:hover:border-kb disabled:opacity-40"
        >
          {t("reset")}
        </button>
      </div>
      {error && (
        <p className="mt-2 text-xs text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2">
          {error}
        </p>
      )}
    </CollapsibleCard>
  );
}
