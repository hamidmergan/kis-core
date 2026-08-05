"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { CaretRight, X } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";
import Checkbox from "@/components/ui/Checkbox";
import IconButton from "@/components/ui/IconButton";
import CollapsibleCard from "@/components/ui/CollapsibleCard";

/**
 * Editor for the CEFR diagnosis question plan.
 *
 * Each row is one question with a task type. Questions carry no level, the AI
 * reads the learner's answers and places them A1 to C2. Option types (multiple
 * choice, reading comprehension, situation) carry their own answer options with a
 * "correct" flag: filled in fully (question plus options with at least one
 * correct), the question is served instantly with no model call and graded in
 * code. Typed types (gap fill) carry a solution instead, one accepted answer per
 * line, since the learner types into the blank rather than picking. Free-text
 * types (error correction, free writing) carry the question and an optional
 * example answer. An incomplete row stays "auto" and the model generates it, so
 * nothing has to be finished before the test works.
 *
 * An empty stored plan means the shipped default is active, so the table falls
 * back to `question_plan_default` (the authored German set) from settings.
 */

type QType =
  | "gap fill" | "multiple choice" | "error correction"
  | "reading comprehension" | "situation" | "free writing";

interface Opt { text: string; correct: boolean }
/** `answers` ist der Lösungsschlüssel als Text, eine Lösung pro Zeile.
 *  `open` ist reine Anzeige und wird nicht gespeichert. */
interface Row { type: QType; text: string; options: Opt[]; answers: string; open?: boolean }
interface PlanItem {
  type: QType;
  text?: string;
  options?: { text: string; correct: boolean }[];
  answers?: string[];
}

const TYPES: QType[] = [
  "gap fill", "multiple choice", "error correction",
  "reading comprehension", "situation", "free writing",
];
const OPTION_TYPES: QType[] = [
  "multiple choice", "reading comprehension", "situation",
];
const TYPED_TYPES: QType[] = ["gap fill"];
const isOptionType = (t: QType) => OPTION_TYPES.includes(t);
const isTypedType = (t: QType) => TYPED_TYPES.includes(t);
const MAX_OPTIONS = 8;
const MAX_ANSWERS = 8;

const emptyOptions = (): Opt[] =>
  Array.from({ length: 4 }, () => ({ text: "", correct: false }));

/** Die Lösungszeilen eines Feldes, leere Zeilen fallen weg. */
const answerLines = (text: string): string[] =>
  text.split("\n").map((line) => line.trim()).filter(Boolean).slice(0, MAX_ANSWERS);

export default function DiagnosisQuestionPlanCard() {
  const t = useTranslations("admin.diagnosisPlanCard");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [answerMax, setAnswerMax] = useState<number>(2000);
  const [defaultPlan, setDefaultPlan] = useState<PlanItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A gap fill saved before typed answers existed still carries options; its
  // correct ones become the solution, so an old plan opens filled in rather than
  // blank. Mirrors the same fallback in parse_question_plan on the backend.
  const toRows = (items: PlanItem[]): Row[] =>
    items.map((s) => ({
      type: s.type,
      text: s.text ?? "",
      options: s.options?.length && isOptionType(s.type)
        ? s.options.map((o) => ({ text: o.text, correct: !!o.correct }))
        : (isOptionType(s.type) ? emptyOptions() : []),
      answers: !isTypedType(s.type)
        ? ""
        : (s.answers?.length
            ? s.answers.join("\n")
            : (s.options ?? []).filter((o) => o.correct).map((o) => o.text).join("\n")),
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

  // Serialize one row. An answer key is only stored when it is usable (an option
  // set with at least two options and one correct, or at least one solution
  // line); otherwise it is dropped and the slot falls back to auto, matching
  // question_mode() on the backend.
  const serialize = (r: Row): PlanItem => {
    const item: PlanItem = { type: r.type };
    if (r.text.trim()) item.text = r.text.trim();
    if (isOptionType(r.type)) {
      const opts = r.options
        .map((o) => ({ text: o.text.trim(), correct: o.correct }))
        .filter((o) => o.text);
      if (opts.length >= 2 && opts.some((o) => o.correct)) item.options = opts;
    }
    if (isTypedType(r.type)) {
      const answers = answerLines(r.answers);
      if (answers.length) item.answers = answers;
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
      // so the editor has something to fill in. A typed type needs no seeding,
      // its solution field is one box that starts empty.
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

  const toggleRow = (i: number) => {
    setRows(rows.map((r, j) => (j === i ? { ...r, open: !r.open } : r)));
  };
  const setAllOpen = (open: boolean) => {
    setRows(rows.map((r) => ({ ...r, open })));
  };

  const addRow = () => {
    const next: Row[] = [...rows, {
      type: "gap fill", text: "", options: [], answers: "", open: true,
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

  // Feld- und Knopfmuster wie im uebrigen Adminbereich (2px Rahmen, Hover kb).
  const inputClass =
    "text-xs px-2 py-1.5 border-2 border-border rounded-md bg-background text-foreground "
    + "transition-colors hover:border-kb focus:outline-none focus:border-kb disabled:opacity-50";
  const buttonClass =
    "text-xs px-3 py-1.5 border-2 border-border rounded-md text-foreground transition-colors "
    + "disabled:opacity-40 enabled:hover:border-kb enabled:hover:text-kb";

  const typeOptions = TYPES.map((ty) => ({ value: ty, label: t(`type.${ty}`) }));
  const allOpen = rows.length > 0 && rows.every((r) => r.open);

  return (
    <CollapsibleCard title={t("title")} description={t("description")}>
      <p className="text-xs text-muted-soft">{t("languageHint")}</p>
      <p className="text-xs text-muted-soft mt-1">{t("freeTextHint")}</p>

      <div className="mt-3 flex flex-col gap-4">
        {rows.map((r, i) => (
          <div key={i} className="rounded-lg border border-border-soft p-3 flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => toggleRow(i)}
                aria-expanded={!!r.open}
                aria-label={t("toggleRow")}
                title={t("toggleRow")}
                className="flex items-center gap-2 text-xs text-muted-soft transition-colors hover:text-kb"
              >
                <CaretRight
                  size={12}
                  weight="bold"
                  className={`flex-shrink-0 transition-transform ${r.open ? "rotate-90" : ""}`}
                />
                <span className="w-4 text-left">{i + 1}</span>
              </button>
              <Select
                value={r.type}
                onChange={(v) => update(i, { type: v as QType })}
                options={typeOptions}
                disabled={saving}
                className="w-52"
              />
              {!r.open && r.text.trim() && (
                <span className="min-w-0 flex-1 truncate text-xs text-muted-soft">
                  {r.text.trim().split("\n").map((l) => l.trim()).filter(Boolean).join(" ")}
                </span>
              )}
              <button
                type="button"
                onClick={() => removeRow(i)}
                disabled={saving}
                className={`ml-auto ${buttonClass}`}
              >
                {t("removeRow")}
              </button>
            </div>

            {r.open && (
              <>
                <label className="text-xs text-muted">{t("questionLabel")}</label>
                <textarea
                  value={r.text}
                  placeholder={t("verbatimPlaceholder")}
                  rows={4}
                  onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
                  onBlur={() => saveRows(rows)}
                  disabled={saving}
                  className={`${inputClass} w-full resize-y`}
                />

                {isTypedType(r.type) && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs text-muted">{t("answersLabel")}</span>
                    <span className="text-2xs text-muted-soft">{t("answersHint")}</span>
                    <textarea
                      value={r.answers}
                      placeholder={t("answersPlaceholder")}
                      rows={2}
                      onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, answers: e.target.value } : x)))}
                      onBlur={() => saveRows(rows)}
                      disabled={saving}
                      className={`${inputClass} w-full resize-y`}
                    />
                  </div>
                )}

                {isOptionType(r.type) && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs text-muted">{t("optionsLabel")}</span>
                    <span className="text-2xs text-muted-soft">{t("optionsHint")}</span>
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
                        <Checkbox
                          checked={o.correct}
                          onChange={(v) => updateOption(i, j, { correct: v }, true)}
                          disabled={saving}
                          label={t("correctLabel")}
                        />
                        {r.options.length > 2 && (
                          <IconButton
                            size="sm"
                            onClick={() => removeOption(i, j)}
                            disabled={saving}
                            aria-label={t("removeOption")}
                            title={t("removeOption")}
                          >
                            <X size={12} weight="bold" />
                          </IconButton>
                        )}
                      </div>
                    ))}
                    {r.options.length < MAX_OPTIONS && (
                      <button
                        type="button"
                        onClick={() => addOption(i)}
                        disabled={saving}
                        className={`self-start ${buttonClass}`}
                      >
                        {t("addOption")}
                      </button>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-3">
        <button
          type="button" onClick={addRow} disabled={saving}
          className={buttonClass}
        >
          {t("addRow")}
        </button>
        <button
          type="button" onClick={reset} disabled={saving}
          className={buttonClass}
        >
          {t("reset")}
        </button>
        {rows.length > 0 && (
          <button
            type="button"
            onClick={() => setAllOpen(!allOpen)}
            className={`ml-auto ${buttonClass}`}
          >
            {allOpen ? t("collapseAll") : t("expandAll")}
          </button>
        )}
      </div>

      <div className="mt-4">
        <label className="text-xs text-muted">{t("answerMaxLabel")}</label>
        <input
          type="number" min={1} max={2000} value={answerMax}
          onChange={(e) => setAnswerMax(Number(e.target.value))}
          onBlur={() => void patch({ language_diagnosis_answer_max_chars: answerMax })}
          disabled={saving}
          className={`ml-2 w-24 ${inputClass}`}
        />
      </div>

      {error && (
        <p className="mt-2 text-xs text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2">
          {error}
        </p>
      )}
    </CollapsibleCard>
  );
}
