"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { UploadSimple } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";

/** One dialog for both ways in: pick a file, or read in a web page by link. */
export function AddMaterialModal({
  open,
  onClose,
  onPickFile,
  onAddLink,
}: {
  open: boolean;
  onClose: () => void;
  onPickFile: () => void;
  onAddLink: (url: string) => Promise<void>;
}) {
  const t = useTranslations("workspace.detail.sources");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const close = () => {
    if (busy) return;
    setUrl("");
    setError(null);
    onClose();
  };

  const submit = async () => {
    const value = url.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onAddLink(value);
      setUrl("");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("linkFailed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title={t("addModalTitle")}
      size="sm"
      closeOnBackdropClick={!busy}
      closeOnEscape={!busy}
    >
      <button
        type="button"
        onClick={() => { onPickFile(); close(); }}
        disabled={busy}
        data-testid="add-material-file"
        className="add-source-btn w-full flex flex-col items-center gap-1 px-3 py-5 rounded-lg border-2 border-dashed transition-colors text-[var(--kb)] border-[rgba(var(--kb-rgb),0.35)] hover:border-[var(--kb)] disabled:opacity-40"
      >
        <UploadSimple size={20} weight="bold" />
        <span className="text-sm font-medium">{t("pickFile")}</span>
        <span className="text-xs" style={{ color: "var(--muted)" }}>{t("pickFileHint")}</span>
      </button>

      <div className="mt-4">
        <div className="text-3xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>
          {t("linkHeading")}
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); void submit(); }}
          className="flex items-center gap-2"
        >
          <input
            value={url}
            disabled={busy}
            placeholder={t("linkPlaceholder")}
            data-testid="add-material-link"
            aria-label={t("linkHeading")}
            aria-describedby={error ? "add-material-link-error" : undefined}
            onChange={(e) => { setUrl(e.target.value); setError(null); }}
            className="flex-1 min-w-0 rounded-lg border px-3 py-2 text-sm focus:outline-none"
            style={{
              backgroundColor: "var(--background)",
              borderColor: error ? "var(--error-border)" : "var(--border)",
              color: "var(--foreground)",
            }}
          />
          <button
            type="submit"
            disabled={busy || !url.trim()}
            className="btn-primary px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 whitespace-nowrap"
          >
            {busy ? <Spinner size="sm" color="current" /> : t("linkSubmit")}
          </button>
        </form>
        {error && (
          <p id="add-material-link-error" className="text-sm mt-2" style={{ color: "var(--error)" }}>{error}</p>
        )}
      </div>
    </Modal>
  );
}
