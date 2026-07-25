"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

/**
 * Per-level example answers (A1, A2, B1, B2).
 *
 * One source of truth used by TWO features: the diagnosis grading (to place
 * free-text answers) and the adaptive chat behaviour (to calibrate how the tutor
 * writes to a learner of that level). Several examples per level are separated by
 * "--" or a line break. Saving an empty field restores the shipped defaults.
 */

type Examples = Record<string, string>;

export default function DiagnosisExamplesCard() {
  const t = useTranslations("admin.diagnosisExamplesCard");
  const [levels, setLevels] = useState<string[]>(["A1", "A2", "B1", "B2"]);
  const [examples, setExamples] = useState<Examples | null>(null);
  const [savedKey, setSavedKey] = useState("");
  const [defaults, setDefaults] = useState<Examples>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Canonical serialisation, so merely viewing the card never re-saves the
  // current values (which would pin defaults and stop future default changes).
  const keyOf = (ex: Examples, lvls: string[]) => {
    const clean: Examples = {};
    for (const lvl of lvls) if ((ex[lvl] ?? "").trim()) clean[lvl] = ex[lvl].trim();
    return JSON.stringify(clean);
  };

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const lvls: string[] = Array.isArray(d.language_diagnosis_example_levels)
          ? d.language_diagnosis_example_levels : ["A1", "A2", "B1", "B2"];
        setLevels(lvls);
        const defs: Examples = d.language_diagnosis_level_examples_default ?? {};
        setDefaults(defs);
        const stored = (d.language_diagnosis_level_examples || "").trim();
        const loaded = stored ? { ...defs, ...JSON.parse(stored) } : { ...defs };
        setExamples(loaded);
        setSavedKey(keyOf(loaded, lvls));
      })
      .catch(() => setExamples({}));
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

  if (examples === null) return null;

  const commit = () => {
    const key = keyOf(examples, levels);
    if (key === savedKey) return;
    setSavedKey(key);
    void patch({ language_diagnosis_level_examples: key });
  };
  const reset = () => {
    const defs = { ...defaults };
    setExamples(defs);
    setSavedKey(keyOf(defs, levels));
    void patch({ language_diagnosis_level_examples: "" });
  };

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="text-sm font-medium text-foreground">
        {t("title")}
        <span className="ml-2 text-xs font-mono font-normal text-muted-soft">{"{examples} {example}"}</span>
      </p>
      <p className="text-xs text-muted mt-1">{t("description")}</p>
      <p className="text-xs text-muted-soft mt-1">{t("hint")}</p>

      <div className="mt-3 flex flex-col gap-2">
        {levels.map((lvl) => (
          <div key={lvl} className="flex items-start gap-2">
            <span className="text-xs font-medium text-foreground w-8 pt-2">{lvl}</span>
            <textarea
              value={examples[lvl] ?? ""}
              onChange={(e) => setExamples({ ...examples, [lvl]: e.target.value })}
              onBlur={commit}
              disabled={saving}
              rows={3}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground focus:outline-none focus:border-kb disabled:opacity-50 resize-y"
            />
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-end">
        <button
          type="button"
          onClick={reset}
          disabled={saving}
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
    </div>
  );
}
