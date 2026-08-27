"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import type { ScheduleListEntry } from "./ScheduleEntryCardGlobal";

/** The same numbers sit in the backend schemas.py as TITLE_MAX and NOTE_MAX. */
const TITLE_MAX = 80;
const NOTE_MAX = 500;

interface Props {
  /** null means create new, otherwise this entry is changed. */
  entry: ScheduleListEntry | null;
  /** Prefilled date when creating, such as after a double click on a day. */
  defaultDate?: string;
  onClose: () => void;
  onSaved: () => void;
}

/** Dialog for private appointments, either one day or a span. */
export default function ScheduleEntryModal({ entry, defaultDate, onClose, onSaved }: Props) {
  const t = useTranslations("schedule.modal");
  const [title, setTitle] = useState(entry?.title ?? "");
  const [due, setDue] = useState(entry?.due_date ?? defaultDate ?? "");
  const [end, setEnd] = useState(entry?.end_date ?? "");
  const [time, setTime] = useState(entry?.due_time ?? "");
  const [note, setNote] = useState(entry?.description ?? "");
  const [isRange, setIsRange] = useState(!!entry?.end_date && entry.end_date !== entry.due_date);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  async function save() {
    if (!title.trim() || !due) return;
    setSaving(true);
    setError(null);
    const body = {
      title: title.trim(),
      description: note.trim() || null,
      due_date: due,
      end_date: isRange && end ? end : null,
      due_time: !isRange && time ? time : null,
    };
    const url = entry
      ? `/api/ai-assistant/schedule/entries/${entry.id}`
      : "/api/ai-assistant/schedule/entries";
    try {
      const r = await fetch(url, {
        method: entry ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(
          entry ? { ...body, clear_end_date: !isRange, clear_time: isRange } : body,
        ),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        setError(typeof err.detail === "string" ? err.detail : t("saveError"));
        return;
      }
      onSaved();
    } catch {
      setError(t("saveError"));
    } finally {
      setSaving(false);
    }
  }

  /** Shows how much room is left and colours when it gets tight. */
  const zaehler = (wert: string, max: number) => (
    <div
      className="text-3xs text-right mt-1"
      style={{ color: wert.length >= max ? "var(--error-strong)" : "var(--muted)" }}
    >
      {wert.length} / {max}
    </div>
  );

  const feld = "w-full text-sm rounded-lg px-3 py-2";
  const feldStil = { border: "1px solid var(--border)", backgroundColor: "var(--background)" };
  const beschriftung = "block text-xs font-bold mb-1.5";

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4"
      style={{ backgroundColor: "rgba(13,31,45,.35)" }}
      onClick={onClose}
      role="presentation"
    >
      <div
        className="w-105 max-w-full rounded-xl p-6"
        style={{ backgroundColor: "var(--background)", boxShadow: "0 20px 50px rgba(13,31,45,.28)" }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <h3 className="text-base font-bold mb-4">{t(entry ? "titleEdit" : "titleNew")}</h3>

        <label className={beschriftung} style={{ color: "var(--muted)" }}>{t("label")}</label>
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={TITLE_MAX}
          className={feld}
          style={feldStil}
        />
        {zaehler(title, TITLE_MAX)}

        <label className="flex items-center gap-2.5 text-sm font-semibold mb-3 cursor-pointer select-none">
          <button
            type="button"
            role="switch"
            aria-checked={isRange}
            onClick={() => setIsRange((v) => !v)}
            className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors"
            style={{ backgroundColor: isRange ? "var(--kb)" : "var(--border)" }}
          >
            <span
              aria-hidden="true"
              className="pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transition"
              style={{ transform: isRange ? "translateX(16px)" : "translateX(0)" }}
            />
          </button>
          {t("multiDay")}
        </label>

        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className={beschriftung} style={{ color: "var(--muted)" }}>
              {t(isRange ? "from" : "date")}
            </label>
            <input type="date" value={due} onChange={(e) => setDue(e.target.value)}
                   className={feld} style={feldStil} />
          </div>
          {isRange ? (
            <div>
              <label className={beschriftung} style={{ color: "var(--muted)" }}>{t("to")}</label>
              <input type="date" value={end} onChange={(e) => setEnd(e.target.value)}
                     className={feld} style={feldStil} />
            </div>
          ) : (
            <div>
              <label className={beschriftung} style={{ color: "var(--muted)" }}>{t("time")}</label>
              <input type="time" value={time} onChange={(e) => setTime(e.target.value)}
                     className={feld} style={feldStil} />
            </div>
          )}
        </div>

        <label className={beschriftung} style={{ color: "var(--muted)" }}>{t("note")}</label>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={NOTE_MAX} rows={3}
                  className={`${feld} resize-y`} style={feldStil} />
        {zaehler(note, NOTE_MAX)}

        <p className="text-xs mt-3 mb-4" style={{ color: "var(--muted)" }}>{t("hint")}</p>
        {error && <p className="text-xs mb-3" style={{ color: "var(--error-strong)" }}>{error}</p>}

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose}
                  className="btn-cancel text-sm font-semibold rounded-full px-4 py-2"
                  style={{ color: "var(--foreground-soft)" }}>
            {t("cancel")}
          </button>
          <button type="button" onClick={save} disabled={saving || !title.trim() || !due}
                  className="btn-primary text-sm font-semibold rounded-full px-4 py-2">
            {t("save")}
          </button>
        </div>
      </div>
    </div>
  );
}
