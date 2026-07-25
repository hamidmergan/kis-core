"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

/**
 * Editor for the CEFR diagnosis question plan.
 *
 * Each row is one question with a task type and a CEFR band, plus an optional
 * verbatim question text. An empty stored plan means the shipped default is
 * active, so the table falls back to `question_plan_default` from the settings
 * endpoint. Saving an empty plan (via reset) restores the default.
 */

type Band = "A1" | "A2" | "B1" | "B2";
type QType =
  | "gap fill" | "multiple choice" | "error correction"
  | "reading comprehension" | "situation" | "free writing";

interface Row { band: Band; type: QType; text: string }

const BANDS: Band[] = ["A1", "A2", "B1", "B2"];
const TYPES: QType[] = [
  "gap fill", "multiple choice", "error correction",
  "reading comprehension", "situation", "free writing",
];

interface PlanItem { band: Band; type: QType; text?: string }

export default function DiagnosisQuestionPlanCard() {
  const t = useTranslations("admin.diagnosisPlanCard");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [answerMax, setAnswerMax] = useState<number>(2000);
  const [defaultPlan, setDefaultPlan] = useState<PlanItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toRows = (items: PlanItem[]): Row[] =>
    items.map((s) => ({ band: s.band, type: s.type, text: s.text ?? "" }));

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const def: PlanItem[] = d.language_diagnosis_question_plan_default ?? [];
        setDefaultPlan(def);
        const stored = (d.language_diagnosis_question_plan_de || "").trim();
        setRows(toRows(stored ? (JSON.parse(stored) as PlanItem[]) : def));
        if (typeof d.language_diagnosis_answer_max_chars === "number") {
          setAnswerMax(d.language_diagnosis_answer_max_chars);
        }
      })
      .catch(() => setRows([]));
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

  const saveRows = (next: Row[]) => {
    const clean = next.map((r) => (r.text.trim()
      ? { band: r.band, type: r.type, text: r.text.trim() }
      : { band: r.band, type: r.type }));
    void patch({ language_diagnosis_question_plan_de: JSON.stringify(clean) });
  };

  if (rows === null) return null;

  const update = (i: number, patchRow: Partial<Row>) => {
    const next = rows.map((r, j) => (j === i ? { ...r, ...patchRow } : r));
    setRows(next);
    saveRows(next);
  };
  const addRow = () => {
    const next = [...rows, { band: "A1" as Band, type: "gap fill" as QType, text: "" }];
    setRows(next);
    saveRows(next);
  };
  const removeRow = (i: number) => {
    const next = rows.filter((_, j) => j !== i);
    setRows(next);
    saveRows(next);
  };
  const reset = () => {
    setRows(toRows(defaultPlan));
    void patch({ language_diagnosis_question_plan_de: "" });
  };

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="text-sm font-medium text-foreground">{t("title")}</p>
      <p className="text-xs text-muted mt-1">{t("description")}</p>

      <div className="mt-3 flex flex-col gap-2">
        {rows.map((r, i) => (
          <div key={i} className="flex flex-wrap items-start gap-2">
            <span className="text-xs text-muted-soft w-6 pt-2">{i + 1}</span>
            <select
              value={r.type}
              onChange={(e) => update(i, { type: e.target.value as QType })}
              disabled={saving}
              className="rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground"
            >
              {TYPES.map((ty) => <option key={ty} value={ty}>{t(`type.${ty}`)}</option>)}
            </select>
            <select
              value={r.band}
              onChange={(e) => update(i, { band: e.target.value as Band })}
              disabled={saving}
              className="rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground"
            >
              {BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
            <input
              type="text"
              value={r.text}
              placeholder={t("verbatimPlaceholder")}
              onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
              onBlur={() => saveRows(rows)}
              disabled={saving}
              className="flex-1 min-w-[12rem] rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground"
            />
            <button
              type="button"
              onClick={() => removeRow(i)}
              disabled={saving}
              className="text-xs px-2 py-1.5 rounded-lg border border-border text-foreground enabled:hover:border-kb"
            >
              {t("removeRow")}
            </button>
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-3">
        <button
          type="button" onClick={addRow} disabled={saving}
          className="text-xs px-3 py-1.5 rounded-lg border border-border text-foreground enabled:hover:border-kb"
        >
          {t("addRow")}
        </button>
        <button
          type="button" onClick={reset} disabled={saving}
          className="text-xs px-3 py-1.5 rounded-lg border border-border text-foreground enabled:hover:border-kb"
        >
          {t("reset")}
        </button>
      </div>

      <div className="mt-4">
        <label className="text-xs text-muted">{t("answerMaxLabel")}</label>
        <input
          type="number" min={1} max={2000} value={answerMax}
          onChange={(e) => setAnswerMax(Number(e.target.value))}
          onBlur={() => void patch({ language_diagnosis_answer_max_chars: answerMax })}
          disabled={saving}
          className="ml-2 w-24 rounded-lg border border-border bg-background px-2 py-1 text-xs text-foreground"
        />
      </div>

      {error && (
        <p className="mt-2 text-xs text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2">
          {error}
        </p>
      )}
    </div>
  );
}
