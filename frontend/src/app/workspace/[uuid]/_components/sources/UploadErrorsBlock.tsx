import { useState } from "react";

export function UploadErrorsBlock({
  errors,
  onDismiss,
}: {
  errors: { filename: string; message: string }[];
  onDismiss: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="mt-2 px-3 py-2 rounded-lg text-sm"
      style={{ backgroundColor: "rgba(220,38,38,0.08)", color: "var(--error-strong)", border: "1px solid rgba(220,38,38,0.25)" }}
    >
      <div className="flex items-start gap-2">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex-1 text-left hover:underline transition-colors"
        >
          {errors.length === 1
            ? `1 Datei fehlgeschlagen`
            : `${errors.length} Dateien fehlgeschlagen`}
          <span className="ml-1 opacity-70">{expanded ? "▾" : "▸"}</span>
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="hover:opacity-70 flex-shrink-0"
          aria-label="Schließen"
        >
          ×
        </button>
      </div>
      {expanded && (
        <ul className="mt-2 space-y-1 list-none">
          {errors.map((e, i) => (
            <li key={i} className="text-xs leading-snug">
              <span className="font-medium break-all">{e.filename}</span>
              <span className="opacity-80">: {e.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
