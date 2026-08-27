"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { CaretRight, X } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";
import Checkbox from "@/components/ui/Checkbox";
import IconButton from "@/components/ui/IconButton";
import CollapsibleCard from "@/components/ui/CollapsibleCard";
import Modal from "@/components/ui/Modal";

/** The assessment question plan: two exercise kinds, every row spelled out. */

type QType = "choice" | "free text";

interface Opt { text: string; correct: boolean }
/** The answer key as text, one answer per line. */
interface Row { type: QType; text: string; options: Opt[]; answers: string; open?: boolean }
interface PlanItem {
  type: string;
  text?: string;
  options?: { text: string; correct: boolean }[];
  answers?: string[];
}

const TYPES: QType[] = ["choice", "free text"];
/** Translation key per kind, without spaces. */
const TYPE_KEYS: Record<QType, string> = { "choice": "choice", "free text": "freeText" };
/** The six old names so a stored plan opens unchanged. */
const LEGACY_TYPES: Record<string, QType> = {
  "multiple choice": "choice",
  "reading comprehension": "choice",
  "situation": "choice",
  "gap fill": "free text",
  "error correction": "free text",
  "free writing": "free text",
};
const toQType = (raw: string): QType =>
  (TYPES.includes(raw as QType) ? (raw as QType) : LEGACY_TYPES[raw] ?? "choice");
const isOptionType = (t: QType) => t === "choice";
const MAX_OPTIONS = 8;
const MAX_ANSWERS = 8;

const emptyOptions = (): Opt[] =>
  Array.from({ length: 4 }, () => ({ text: "", correct: false }));

/** The answer lines of a field, empty lines are dropped. */
const answerLines = (text: string): string[] =>
  text.split("\n").map((line) => line.trim()).filter(Boolean).slice(0, MAX_ANSWERS);

export default function DiagnosisQuestionPlanCard() {
  const t = useTranslations("admin.diagnosisPlanCard");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [defaultPlan, setDefaultPlan] = useState<PlanItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [askGenerate, setAskGenerate] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // For an old cloze the correct options become the answer key.
  const toRows = (items: PlanItem[]): Row[] =>
    items.map((s) => {
      const type = toQType(s.type);
      return {
        type,
        text: s.text ?? "",
        options: s.options?.length && isOptionType(type)
          ? s.options.map((o) => ({ text: o.text, correct: !!o.correct }))
          : (isOptionType(type) ? emptyOptions() : []),
        answers: isOptionType(type)
          ? ""
          : (s.answers?.length
              ? s.answers.join("\n")
              : (s.type === "gap fill" ? (s.options ?? []) : [])
                  .filter((o) => o.correct).map((o) => o.text).join("\n")),
      };
    });

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const def: PlanItem[] = d.language_diagnosis_question_plan_default ?? [];
        setDefaultPlan(def);
        const stored = (d.language_diagnosis_question_plan_de || "").trim();
        setRows(toRows(stored ? (JSON.parse(stored) as PlanItem[]) : def));
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

  // An unusable option set is dropped, an empty answer is not an error.
  const serialize = (r: Row): PlanItem => {
    const item: PlanItem = { type: r.type };
    if (r.text.trim()) item.text = r.text.trim();
    if (isOptionType(r.type)) {
      const opts = r.options
        .map((o) => ({ text: o.text.trim(), correct: o.correct }))
        .filter((o) => o.text);
      if (opts.length >= 2 && opts.some((o) => o.correct)) item.options = opts;
    } else {
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
      // A new choice question gets empty option fields, free text needs none.
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
      type: "choice", text: "", options: emptyOptions(), answers: "", open: true,
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

  // The AI writes the sentence once, after that it is as if typed by hand.
  const generate = async () => {
    setAskGenerate(false);
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/settings/diagnosis-plan/generate", {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        let detail = t("generateFailed");
        try {
          const body = await res.json();
          if (typeof body?.detail === "string") detail = body.detail;
        } catch { /* ignore */ }
        setError(detail);
        return;
      }
      const body = await res.json();
      const next = toRows((body?.questions ?? []) as PlanItem[]);
      if (!next.length) {
        setError(t("generateFailed"));
        return;
      }
      setRows(next);
      saveRows(next);
    } catch {
      setError(t("generateFailed"));
    } finally {
      setGenerating(false);
    }
  };

  // Field and button style as in the rest of the admin area.
  const inputClass =
    "text-xs px-2 py-1.5 border-2 border-border rounded-md bg-background text-foreground "
    + "transition-colors hover:border-kb focus:outline-none focus:border-kb disabled:opacity-50";
  const buttonClass =
    "text-xs px-3 py-1.5 border-2 border-border rounded-md text-foreground transition-colors "
    + "disabled:opacity-40 enabled:hover:border-kb enabled:hover:text-kb";

  const typeOptions = TYPES.map((ty) => ({ value: ty, label: t(`type.${TYPE_KEYS[ty]}`) }));
  const allOpen = rows.length > 0 && rows.every((r) => r.open);
  // While the AI writes, nobody may type alongside.
  const busy = saving || generating;

  // The card starts open, collapsed the assessment looks empty.
  return (
    <CollapsibleCard title={t("title")} description={t("description")} defaultOpen>
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
                disabled={busy}
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
                disabled={busy}
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
                  disabled={busy}
                  className={`${inputClass} w-full resize-y`}
                />

                {/* Freitext: die Lösung ist FREIWILLIG und genau das ist der
                    Schalter. Steht eine da, prüft der Code Wort für Wort und der
                    Test bleibt ohne KI. Bleibt sie leer, beurteilt die KI die
                    Antwort am Ende, und nur solche Zeilen tragen die Stufe. Der
                    Hinweis darunter sagt live, was gerade gilt, damit niemand
                    raten muss, was das leere Feld bedeutet. */}
                {!isOptionType(r.type) && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs text-muted">{t("answersLabel")}</span>
                    <span className="text-2xs text-muted-soft">{t("answersHint")}</span>
                    {/* Kein Platzhalter: ein Beispielwort im leeren Feld sah aus
                        wie eine schon eingetragene Lösung, und leer heißt hier
                        etwas ganz Bestimmtes, nämlich dass die KI beurteilt. */}
                    <textarea
                      value={r.answers}
                      rows={2}
                      onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, answers: e.target.value } : x)))}
                      onBlur={() => saveRows(rows)}
                      disabled={busy}
                      className={`${inputClass} w-full resize-y`}
                    />
                    <span className="text-2xs text-muted-soft">
                      {answerLines(r.answers).length
                        ? t("gradedByCodeHint")
                        : t("gradedByAiHint")}
                    </span>
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
                          disabled={busy}
                          className={`${inputClass} flex-1 min-w-[10rem]`}
                        />
                        <Checkbox
                          checked={o.correct}
                          onChange={(v) => updateOption(i, j, { correct: v }, true)}
                          disabled={busy}
                          label={t("correctLabel")}
                        />
                        {r.options.length > 2 && (
                          <IconButton
                            size="sm"
                            onClick={() => removeOption(i, j)}
                            disabled={busy}
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
                        disabled={busy}
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

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button" onClick={addRow} disabled={busy}
          className={buttonClass}
        >
          {t("addRow")}
        </button>
        <button
          type="button"
          onClick={() => (rows.length ? setAskGenerate(true) : void generate())}
          disabled={busy}
          className={buttonClass}
        >
          {generating ? t("generating") : t("generate")}
        </button>
        <button
          type="button" onClick={reset} disabled={busy}
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

      {generating && (
        <p className="mt-2 text-xs text-muted-soft">{t("generatingHint")}</p>
      )}

      <Modal
        open={askGenerate}
        onClose={() => setAskGenerate(false)}
        title={t("generate")}
        footer={
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setAskGenerate(false)} className={buttonClass}>
              {t("generateCancel")}
            </button>
            <button type="button" onClick={() => void generate()} className={buttonClass}>
              {t("generateConfirm")}
            </button>
          </div>
        }
      >
        {/* Der Knopf folgt der ausgelieferten Typen-Folge, nicht der aktuellen
            Liste. Anzahl und Aufgabenarten aendern sich also, und das muss vorher
            dastehen. Die Zahl kommt aus dem Standardplan, damit sie stimmt, falls
            die Folge sich einmal aendert. Das Fenster oeffnet nur bei gefuellter
            Liste, und die kommt aus derselben Antwort wie der Standardplan, also
            steht hier nie eine Null. */}
        <p className="text-sm text-foreground">
          {t("generateWarningResult", { count: defaultPlan.length })}
        </p>
      </Modal>

      {error && (
        <p className="mt-2 text-xs text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2">
          {error}
        </p>
      )}
    </CollapsibleCard>
  );
}
