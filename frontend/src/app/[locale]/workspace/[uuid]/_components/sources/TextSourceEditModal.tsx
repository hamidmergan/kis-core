"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import type { Source } from "../../_types";
import { TextSourceArea } from "./TextSourceArea";

/** Edits the pasted text of a text source, saving reads the source in again. */
export function TextSourceEditModal({
  source,
  workspaceUuid,
  maxChars,
  onClose,
  onSave,
}: {
  source: Source | null;
  workspaceUuid: string;
  maxChars: number;
  onClose: () => void;
  onSave: (sourceUuid: string, text: string) => Promise<void>;
}) {
  const t = useTranslations("workspace.detail.sources");
  const [text, setText] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!source) return;
    let cancelled = false;
    setText(null);
    setError(null);
    fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/text`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d: { text: string }) => { if (!cancelled) setText(d.text); })
      .catch(() => { if (!cancelled) setError(t("textLoadFailed")); });
    return () => { cancelled = true; };
  }, [source, workspaceUuid, t]);

  const close = () => { if (!busy) onClose(); };
  const value = text ?? "";
  const canSave = text !== null && !!value.trim() && value.trim().length <= maxChars && !busy;

  const save = async () => {
    if (!source || !canSave) return;
    setBusy(true);
    setError(null);
    try {
      await onSave(source.uuid, value.trim());
      onClose();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : t("textSaveFailed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={!!source}
      onClose={close}
      title={t("editText")}
      size="lg"
      closeOnBackdropClick={!busy}
      closeOnEscape={!busy}
      footer={
        <div className="flex justify-end gap-2">
          <button type="button" onClick={close} disabled={busy} className="btn-secondary px-4 py-2 rounded-lg text-sm font-medium">
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={!canSave}
            data-testid="text-source-save"
            className="btn-primary px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
          >
            {busy ? <Spinner size="sm" color="current" /> : t("textSave")}
          </button>
        </div>
      }
    >
      {text === null && !error ? (
        <div className="flex justify-center py-8"><Spinner size="md" /></div>
      ) : (
        text !== null && (
          <TextSourceArea value={value} onChange={setText} maxChars={maxChars} disabled={busy} rows={14} error={!!error} testId="text-source-edit" />
        )
      )}
      {error && <p className="text-sm mt-2" style={{ color: "var(--error)" }}>{error}</p>}
    </Modal>
  );
}
