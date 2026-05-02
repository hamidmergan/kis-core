import { useState } from "react";
import { useTranslations } from "next-intl";

export function UploadErrorsBlock({
  errors,
  onDismiss,
}: {
  errors: { filename: string; message: string }[];
  onDismiss: () => void;
}) {
  const t = useTranslations("workspace.detail.sources.uploadErrors");
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="mt-2 px-3 py-2 rounded-lg text-base"
      style={{ backgroundColor: "rgba(220,38,38,0.08)", color: "var(--error-strong)", border: "1px solid rgba(220,38,38,0.25)" }}
    >
      <div className="flex items-start gap-2">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex-1 text-left hover:underline transition-colors"
        >
          {errors.length === 1 ? t("single") : t("multi", { n: errors.length })}
          <span className="ml-1 opacity-70">{expanded ? "▾" : "▸"}</span>
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="hover:text-kb transition-colors flex-shrink-0"
          aria-label={t("dismiss")}
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
