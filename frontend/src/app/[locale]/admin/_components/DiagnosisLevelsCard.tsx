"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import CollapsibleCard from "@/components/ui/CollapsibleCard";

/**
 * Die Stufen-Leiter A1 bis C2: je Stufe eine Beschreibung und Beispielsaetze.
 *
 * EINE Quelle fuer DREI Verwendungen: die Diagnose stuft daran ein, der Chat und
 * die Werkzeuge schreiben daran entlang. Ersetzt die frühere Karte
 * "Sprachniveau-Beispiele" und die Stufen-Liste, die vorher im englischen
 * Prompt-Text stand, damit ein Sprachexperte auf Deutsch und ohne Platzhalter
 * pflegt. Ein leeres Feld stellt den ausgelieferten Standard wieder her.
 */

type PerLevel = Record<string, string>;

export default function DiagnosisLevelsCard() {
  const t = useTranslations("admin.diagnosisLevelsCard");
  const [levels, setLevels] = useState<string[]>(["A1", "A2", "B1", "B2", "C1", "C2"]);
  const [descriptions, setDescriptions] = useState<PerLevel | null>(null);
  const [examples, setExamples] = useState<PerLevel>({});
  const [savedDescriptions, setSavedDescriptions] = useState("");
  const [savedExamples, setSavedExamples] = useState("");
  const [descriptionDefaults, setDescriptionDefaults] = useState<PerLevel>({});
  const [exampleDefaults, setExampleDefaults] = useState<PerLevel>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Kanonische Form, damit blosses Anschauen nie speichert (das wuerde die
  // aktuellen Standards festschreiben und kuenftige Aenderungen daran verdecken).
  const keyOf = (values: PerLevel, lvls: string[]) => {
    const clean: PerLevel = {};
    for (const lvl of lvls) if ((values[lvl] ?? "").trim()) clean[lvl] = values[lvl].trim();
    return JSON.stringify(clean);
  };

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const lvls: string[] = Array.isArray(d.language_diagnosis_example_levels)
          ? d.language_diagnosis_example_levels : ["A1", "A2", "B1", "B2", "C1", "C2"];
        setLevels(lvls);

        const descDefs: PerLevel = d.language_diagnosis_level_descriptions_default ?? {};
        const exDefs: PerLevel = d.language_diagnosis_level_examples_default ?? {};
        setDescriptionDefaults(descDefs);
        setExampleDefaults(exDefs);

        const storedDesc = (d.language_diagnosis_level_descriptions || "").trim();
        const storedEx = (d.language_diagnosis_level_examples || "").trim();
        const loadedDesc = storedDesc ? { ...descDefs, ...JSON.parse(storedDesc) } : { ...descDefs };
        const loadedEx = storedEx ? { ...exDefs, ...JSON.parse(storedEx) } : { ...exDefs };
        setDescriptions(loadedDesc);
        setExamples(loadedEx);
        setSavedDescriptions(keyOf(loadedDesc, lvls));
        setSavedExamples(keyOf(loadedEx, lvls));
      })
      .catch(() => setDescriptions({}));
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

  if (descriptions === null) return null;

  const commitDescriptions = () => {
    const key = keyOf(descriptions, levels);
    if (key === savedDescriptions) return;
    setSavedDescriptions(key);
    void patch({ language_diagnosis_level_descriptions: key });
  };
  const commitExamples = () => {
    const key = keyOf(examples, levels);
    if (key === savedExamples) return;
    setSavedExamples(key);
    void patch({ language_diagnosis_level_examples: key });
  };
  const reset = () => {
    const descs = { ...descriptionDefaults };
    const exs = { ...exampleDefaults };
    setDescriptions(descs);
    setExamples(exs);
    setSavedDescriptions(keyOf(descs, levels));
    setSavedExamples(keyOf(exs, levels));
    void patch({
      language_diagnosis_level_descriptions: "",
      language_diagnosis_level_examples: "",
    });
  };

  return (
    <CollapsibleCard title={t("title")} description={t("description")} defaultOpen>
      <p className="text-xs text-muted-soft">{t("hint")}</p>

      <div className="mt-3 flex flex-col gap-2">
        {levels.map((lvl) => (
          <div
            key={lvl}
            className="flex items-start gap-3 rounded-lg border border-border-soft bg-surface px-3 py-3"
          >
            <span className="w-10 shrink-0 rounded-md bg-kb20 py-1 text-center text-xs font-medium text-kb">
              {lvl}
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <div>
                <label className="block text-2xs text-muted-soft" htmlFor={`level-desc-${lvl}`}>
                  {t("descriptionLabel")}
                </label>
                <textarea
                  id={`level-desc-${lvl}`}
                  value={descriptions[lvl] ?? ""}
                  onChange={(e) => setDescriptions({ ...descriptions, [lvl]: e.target.value })}
                  onBlur={commitDescriptions}
                  disabled={saving}
                  rows={2}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground focus:outline-none focus:border-kb disabled:opacity-50 resize-y"
                />
              </div>
              <div>
                <label className="block text-2xs text-muted-soft" htmlFor={`level-ex-${lvl}`}>
                  {t("examplesLabel")}
                </label>
                <textarea
                  id={`level-ex-${lvl}`}
                  value={examples[lvl] ?? ""}
                  onChange={(e) => setExamples({ ...examples, [lvl]: e.target.value })}
                  onBlur={commitExamples}
                  disabled={saving}
                  rows={3}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground focus:outline-none focus:border-kb disabled:opacity-50 resize-y"
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-2 flex items-center justify-between gap-3">
        <p className="text-2xs text-muted-soft">{t("examplesHint")}</p>
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
    </CollapsibleCard>
  );
}
