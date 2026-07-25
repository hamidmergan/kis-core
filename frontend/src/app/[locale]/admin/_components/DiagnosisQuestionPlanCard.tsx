"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

/**
 * Editor for the CEFR diagnosis question plan.
 *
 * Each row is one question with a task type and a CEFR band. Option types (gap
 * fill, multiple choice, reading comprehension, situation) carry their own answer
 * options with a "correct" flag: filled in fully (question plus options with at
 * least one correct), the question is served instantly with no model call and
 * graded in code. Free-text types (error correction, free writing) carry the
 * question and an optional example answer. An incomplete option row stays "auto"
 * and the model generates it, so nothing has to be finished before the test works.
 *
 * An empty stored plan means the shipped default is active, so the table falls
 * back to `question_plan_default` (the authored German set) from settings.
 */

type Band = "A1" | "A2" | "B1" | "B2";
type QType =
  | "gap fill" | "multiple choice" | "error correction"
  | "reading comprehension" | "situation" | "free writing";

interface Opt { text: string; correct: boolean }
interface Row { band: Band; type: QType; text: string; options: Opt[]; example: string }
interface PlanItem {
  band: Band;
  type: QType;
  text?: string;
  options?: { text: string; correct: boolean }[];
  example?: string;
}

const BANDS: Band[] = ["A1", "A2", "B1", "B2"];
const TYPES: QType[] = [
  "gap fill", "multiple choice", "error correction",
  "reading comprehension", "situation", "free writing",
];
const OPTION_TYPES: QType[] = [
  "gap fill", "multiple choice", "reading comprehension", "situation",
];
const isOptionType = (t: QType) => OPTION_TYPES.includes(t);
const MAX_OPTIONS = 8;

const emptyOptions = (): Opt[] =>
  Array.from({ length: 4 }, () => ({ text: "", correct: false }));

export default function DiagnosisQuestionPlanCard() {
  const t = useTranslations("admin.diagnosisPlanCard");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [answerMax, setAnswerMax] = useState<number>(2000);
  const [defaultPlan, setDefaultPlan] = useState<PlanItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toRows = (items: PlanItem[]): Row[] =>
    items.map((s) => ({
      band: s.band,
      type: s.type,
      text: s.text ?? "",
      options: s.options?.length
        ? s.options.map((o) => ({ text: o.text, correct: !!o.correct }))
        : (isOptionType(s.type) ? emptyOptions() : []),
      example: s.example ?? "",
    }));

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

  // Serialize one row. An option set is only stored when it is a usable key (at
  // least two options and at least one correct); otherwise it is dropped and the
  // slot falls back to auto, matching question_mode() on the backend.
  const serialize = (r: Row): PlanItem => {
    const item: PlanItem = { band: r.band, type: r.type };
    if (r.text.trim()) item.text = r.text.trim();
    if (isOptionType(r.type)) {
      const opts = r.options
        .map((o) => ({ text: o.text.trim(), correct: o.correct }))
        .filter((o) => o.text);
      if (opts.length >= 2 && opts.some((o) => o.correct)) item.options = opts;
    } else if (r.example.trim()) {
      item.example = r.example.trim();
    }
    return item;
  };

  const saveRows = (next: Row[]) => {
    void patch({ language_diagnosis_question_plan_de: JSON.stringify(next.map(serialize)) });
  };

  if (rows === null) return null;

  const update = (i: number, patchRow: Partial<Row>) => {
    const next = rows.map((r, j) => {
      if (j !== i) return r;
      const merged = { ...r, ...patchRow };
      // Switching to an option type with no options yet: seed the empty fields
      // so the editor has something to fill in.
      if (patchRow.type && isOptionType(patchRow.type) && merged.options.length === 0) {
        merged.options = emptyOptions();
      }
      return merged;
    });
    setRows(next);
    saveRows(next);
  };

  const updateOption = (i: number, j: number, patchOpt: Partial<Opt>, save: boolean) => {
    const next = rows.map((r, ri) =>
      ri === i
        ? { ...r, options: r.options.map((o, oi) => (oi === j ? { ...o, ...patchOpt } : o)) }
        : r,
    );
    setRows(next);
    if (save) saveRows(next);
  };

  const addOption = (i: number) => {
    const next = rows.map((r, ri) =>
      ri === i && r.options.length < MAX_OPTIONS
        ? { ...r, options: [...r.options, { text: "", correct: false }] }
        : r,
    );
    setRows(next);
    saveRows(next);
  };

  const removeOption = (i: number, j: number) => {
    const next = rows.map((r, ri) =>
      ri === i ? { ...r, options: r.options.filter((_, oi) => oi !== j) } : r,
    );
    setRows(next);
    saveRows(next);
  };

  const addRow = () => {
    const next: Row[] = [...rows, {
      band: "A1", type: "gap fill", text: "", options: emptyOptions(), example: "",
    }];
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

  const inputClass =
    "rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground";

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="text-sm font-medium text-foreground">{t("title")}</p>
      <p className="text-xs text-muted mt-1">{t("description")}</p>
      <p className="text-xs text-muted-soft mt-1">{t("languageHint")}</p>

      <div className="mt-3 flex flex-col gap-4">
        {rows.map((r, i) => (
          <div key={i} className="rounded-lg border border-border-soft p-3 flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-soft w-6">{i + 1}</span>
              <select
                value={r.type}
                onChange={(e) => update(i, { type: e.target.value as QType })}
                disabled={saving}
                className={inputClass}
              >
                {TYPES.map((ty) => <option key={ty} value={ty}>{t(`type.${ty}`)}</option>)}
              </select>
              <select
                value={r.band}
                onChange={(e) => update(i, { band: e.target.value as Band })}
                disabled={saving}
                className={inputClass}
              >
                {BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
              <button
                type="button"
                onClick={() => removeRow(i)}
                disabled={saving}
                className="ml-auto text-xs px-2 py-1.5 rounded-lg border border-border text-foreground enabled:hover:border-kb"
              >
                {t("removeRow")}
              </button>
            </div>

            <label className="text-xs text-muted">{t("questionLabel")}</label>
            <textarea
              value={r.text}
              placeholder={t("verbatimPlaceholder")}
              rows={2}
              onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
              onBlur={() => saveRows(rows)}
              disabled={saving}
              className={`${inputClass} w-full resize-y`}
            />

            {isOptionType(r.type) ? (
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted">{t("optionsLabel")}</span>
                <span className="text-[11px] text-muted-soft">{t("optionsHint")}</span>
                {r.options.map((o, j) => (
                  <div key={j} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={o.text}
                      placeholder={t("optionPlaceholder")}
                      onChange={(e) => updateOption(i, j, { text: e.target.value }, false)}
                      onBlur={() => saveRows(rows)}
                      disabled={saving}
                      className={`${inputClass} flex-1 min-w-[10rem]`}
                    />
                    <label className="flex items-center gap-1 text-xs text-foreground whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={o.correct}
                        onChange={(e) => updateOption(i, j, { correct: e.target.checked }, true)}
                        disabled={saving}
                      />
                      {t("correctLabel")}
                    </label>
                    {r.options.length > 2 && (
                      <button
                        type="button"
                        onClick={() => removeOption(i, j)}
                        disabled={saving}
                        aria-label={t("removeOption")}
                        className="text-xs px-2 py-1 rounded-lg border border-border text-foreground enabled:hover:border-kb"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
                {r.options.length < MAX_OPTIONS && (
                  <button
                    type="button"
                    onClick={() => addOption(i)}
                    disabled={saving}
                    className="self-start text-xs px-2 py-1 rounded-lg border border-border text-foreground enabled:hover:border-kb"
                  >
                    {t("addOption")}
                  </button>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted">{t("exampleLabel")}</label>
                <textarea
                  value={r.example}
                  placeholder={t("examplePlaceholder")}
                  rows={2}
                  onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, example: e.target.value } : x)))}
                  onBlur={() => saveRows(rows)}
                  disabled={saving}
                  className={`${inputClass} w-full resize-y`}
                />
              </div>
            )}
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
