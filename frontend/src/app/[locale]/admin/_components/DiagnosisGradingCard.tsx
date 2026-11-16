"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import CollapsibleCard from "@/components/ui/CollapsibleCard";
import { useSettingsPatch } from "./useSettingsPatch";

/** The grading rules of the assessment, empty resets to the default. */
export default function DiagnosisGradingCard() {
  const t = useTranslations("admin.diagnosisGradingCard");
  const [rules, setRules] = useState<string | null>(null);
  const [savedRules, setSavedRules] = useState("");
  const [fallback, setFallback] = useState("");
  const { saving, error, setError, patch } = useSettingsPatch(t("saveFailed"));

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

  if (rules === null) return null;

  // Save only on a real change, otherwise just looking freezes the default.
  const commit = async () => {
    if (rules === savedRules) return;
    // Only a stored text counts as saved, a failed save runs again on the next blur.
    if (await patch({ language_diagnosis_grading_rules: rules })) setSavedRules(rules);
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
        onBlur={() => void commit()}
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
