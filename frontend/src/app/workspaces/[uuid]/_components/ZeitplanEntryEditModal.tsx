import { useEffect, useState } from "react";
import { X } from "@phosphor-icons/react";
import type { ZeitplanEntry, ZeitplanEntryType } from "../_types";

export interface EditInput {
  type: ZeitplanEntryType;
  title: string;
  description: string;
  due_date: string;      // '' == leer
  due_time: string;      // '' == leer
  is_optional: boolean;
}

export function ZeitplanEntryEditModal({
  initial,
  title,
  submitLabel,
  onCancel,
  onSubmit,
}: {
  initial?: ZeitplanEntry;
  title: string;
  submitLabel: string;
  onCancel: () => void;
  onSubmit: (input: EditInput) => Promise<void> | void;
}) {
  const [titleVal, setTitleVal] = useState(initial?.title || "");
  const [description, setDescription] = useState(initial?.description || "");
  const [dueDate, setDueDate] = useState(initial?.due_date || "");
  const [dueTime, setDueTime] = useState(initial?.due_time || "");
  const [isOptional, setIsOptional] = useState(initial?.is_optional || false);
  const [submitting, setSubmitting] = useState(false);

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
      onClick={onCancel}
    >
      <form
        className="rounded-2xl w-full max-w-md p-5"
        style={{ backgroundColor: "var(--bg)" }}
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold" style={{ color: "var(--text)" }}>{title}</h3>
          <button
            type="button"
            onClick={onCancel}
            className="w-7 h-7 rounded-full flex items-center justify-center hover:opacity-70"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
            aria-label="Schließen"
          >
            <X size={14} weight="bold" />
          </button>
        </div>

        <div className="space-y-3 text-sm">
          <label className="block">
            <span className="text-xs font-medium block mb-1" style={{ color: "var(--muted)" }}>Titel</span>
            <input
              type="text"
              required
              maxLength={200}
              value={titleVal}
              onChange={(e) => setTitleVal(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm"
              style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text)" }}
            />
          </label>

          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <span className="text-xs font-medium block mb-1" style={{ color: "var(--muted)" }}>Datum</span>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-sm"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text)" }}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium block mb-1" style={{ color: "var(--muted)" }}>Uhrzeit</span>
              <input
                type="time"
                value={dueTime}
                onChange={(e) => setDueTime(e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-sm"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text)" }}
              />
            </label>
          </div>

          <label className="block">
            <span className="text-xs font-medium block mb-1" style={{ color: "var(--muted)" }}>Beschreibung (optional)</span>
            <textarea
              rows={3}
              maxLength={2000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm resize-none"
              style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text)" }}
            />
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={isOptional}
              onChange={(e) => setIsOptional(e.target.checked)}
            />
            <span className="text-xs" style={{ color: "var(--text)" }}>Optional (freiwillig)</span>
          </label>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-lg text-xs font-semibold"
            style={{ color: "var(--muted)", backgroundColor: "var(--surface-dim)" }}
          >
            Abbrechen
          </button>
          <button
            type="submit"
            disabled={submitting || !titleVal.trim()}
            className="px-4 py-2 rounded-lg text-xs font-semibold disabled:opacity-40"
            style={{ color: "#fff", backgroundColor: "var(--accent)" }}
          >
            {submitting ? "..." : submitLabel}
          </button>
        </div>
      </form>
    </div>
  );
}
