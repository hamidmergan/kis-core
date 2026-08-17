import { useEffect, useRef, useState } from "react";
import { backdropClose, newBackdropPress } from "@/components/ui/backdropClose";
import { useTranslations } from "next-intl";
import { Check, X } from "@phosphor-icons/react";
import type { ScheduleEntry, ScheduleEntryType } from "../../_types";
import { SCHEDULE_TITLE_MAX, SCHEDULE_DESCRIPTION_MAX } from "../../_constants";

export interface EditInput {
  type: ScheduleEntryType;
  title: string;
  description: string;
  due_date: string;      // '' == leer
  due_time: string;      // '' == leer
  // 'month' heisst: nur der Monat ist bekannt. due_date traegt dann den Monatsersten
  // als Sortierpunkt, die Zeitleiste zeigt ihn nie als Tagesnummer.
  date_precision: "day" | "month";
  is_optional: boolean;
}

export function ScheduleEntryEditModal({
  initial,
  title,
  submitLabel,
  onCancel,
  onSubmit,
}: {
  initial?: ScheduleEntry;
  title: string;
  submitLabel: string;
  onCancel: () => void;
  onSubmit: (input: EditInput) => Promise<void> | void;
}) {
  const t = useTranslations("workspace.detail.studio.schedule.modal");
  const press = useRef(newBackdropPress()).current;
  const [titleVal, setTitleVal] = useState(initial?.title || "");
  const [description, setDescription] = useState(initial?.description || "");
  const [dueDate, setDueDate] = useState(initial?.due_date || "");
  const [dueTime, setDueTime] = useState(initial?.due_time || "");
  const [monthOnly, setMonthOnly] = useState(initial?.date_precision === "month");
  const [isOptional, setIsOptional] = useState(initial?.is_optional || false);
  const [submitting, setSubmitting] = useState(false);

  // Der Haken schaltet nur die Anzeige um. Gespeichert wird immer ein volles Datum,
  // bei "nur Monat" der Monatserste.
  function toggleMonthOnly() {
    const next = !monthOnly;
    setMonthOnly(next);
    if (next && dueDate) setDueDate(`${dueDate.slice(0, 7)}-01`);
  }

  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel(); };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [onCancel]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!titleVal.trim()) return;
    setSubmitting(true);
    try {
      await onSubmit({
        type: initial?.type || "deadline",
        title: titleVal.trim(),
        description: description.trim(),
        due_date: dueDate,
        due_time: dueTime,
        date_precision: monthOnly ? "month" : "day",
        is_optional: isOptional,
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
      {...backdropClose(press, onCancel)}
    >
      <form
        className="rounded-2xl w-full max-w-md p-5"
        style={{ backgroundColor: "var(--background)" }}
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold" style={{ color: "var(--foreground)" }}>{title}</h3>
          <button
            type="button"
            onClick={onCancel}
            className="w-7 h-7 rounded-full flex items-center justify-center btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}
            aria-label={t("close")}
          >
            <X size={14} weight="bold" />
          </button>
        </div>

        <div className="space-y-3 text-base">
          <label className="block">
            <span className="text-sm font-medium block mb-1" style={{ color: "var(--muted)" }}>{t("titleField")}</span>
            <input
              type="text"
              required
              maxLength={SCHEDULE_TITLE_MAX}
              value={titleVal}
              onChange={(e) => setTitleVal(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-base border-2 border-[var(--border)] hover:border-[var(--kb)] focus:border-[var(--kb)] focus:outline-none transition-colors"
              style={{ backgroundColor: "var(--surface)", color: "var(--foreground)" }}
            />
          </label>

          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <span className="text-sm font-medium block mb-1" style={{ color: "var(--muted)" }}>{t("dateField")}</span>
              <input
                type={monthOnly ? "month" : "date"}
                value={monthOnly ? dueDate.slice(0, 7) : dueDate}
                onChange={(e) =>
                  setDueDate(monthOnly && e.target.value ? `${e.target.value}-01` : e.target.value)
                }
                className="w-full px-3 py-2 rounded-lg text-base border-2 border-[var(--border)] hover:border-[var(--kb)] focus:border-[var(--kb)] focus:outline-none transition-colors"
                style={{ backgroundColor: "var(--surface)", color: "var(--foreground)" }}
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium block mb-1" style={{ color: "var(--muted)" }}>{t("timeField")}</span>
              <input
                type="time"
                value={dueTime}
                onChange={(e) => setDueTime(e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-base border-2 border-[var(--border)] hover:border-[var(--kb)] focus:border-[var(--kb)] focus:outline-none transition-colors"
                style={{ backgroundColor: "var(--surface)", color: "var(--foreground)" }}
              />
            </label>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <button
              type="button"
              onClick={toggleMonthOnly}
              aria-label={monthOnly ? t("notMonthOnlyAria") : t("monthOnlyAria")}
              className={`flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors border-2 ${
                monthOnly
                  ? "border-[var(--kb)] bg-[var(--kb)]"
                  : "border-[var(--border)] bg-background hover:border-[var(--kb)]"
              }`}
              style={{ color: "#fff" }}
            >
              {monthOnly && <Check size={11} weight="bold" />}
            </button>
            <span className="text-sm" style={{ color: "var(--foreground)" }}>{t("monthOnlyLabel")}</span>
          </label>

          <label className="block">
            <span className="text-sm font-medium block mb-1" style={{ color: "var(--muted)" }}>{t("descriptionField")}</span>
            <textarea
              rows={3}
              maxLength={SCHEDULE_DESCRIPTION_MAX}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-base resize-none border-2 border-[var(--border)] hover:border-[var(--kb)] focus:border-[var(--kb)] focus:outline-none transition-colors"
              style={{ backgroundColor: "var(--surface)", color: "var(--foreground)" }}
            />
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <button
              type="button"
              onClick={() => setIsOptional(!isOptional)}
              aria-label={isOptional ? t("notOptionalAria") : t("optionalAria")}
              className={`flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors border-2 ${
                isOptional
                  ? "border-[var(--kb)] bg-[var(--kb)]"
                  : "border-[var(--border)] bg-background hover:border-[var(--kb)]"
              }`}
              style={{ color: "#fff" }}
            >
              {isOptional && <Check size={11} weight="bold" />}
            </button>
            <span className="text-sm" style={{ color: "var(--foreground)" }}>{t("optionalLabel")}</span>
          </label>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="btn-cancel px-4 py-2 rounded-lg text-xs font-semibold text-[var(--muted)] bg-[var(--surface-dim)]"
          >
            {t("cancel")}
          </button>
          <button
            type="submit"
            disabled={submitting || !titleVal.trim()}
            className="btn-fill-accent px-4 py-2 rounded-lg text-xs font-semibold transition-colors disabled:opacity-40"
          >
            {submitting ? t("submitting") : submitLabel}
          </button>
        </div>
      </form>
    </div>
  );
}
