"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { WORKSPACE_TITLE_MAX, WORKSPACE_DESCRIPTION_MAX } from "../_shared";

interface EditWorkspaceModalProps {
  currentTitle: string;
  currentDescription: string;
  onClose: () => void;
  onSubmit: (newTitle: string, newDescription: string) => Promise<boolean>;
}

export default function EditWorkspaceModal({
  currentTitle,
  currentDescription,
  onClose,
  onSubmit,
}: EditWorkspaceModalProps) {
  const t = useTranslations("workspace.list");
  const labels = useWorkspaceLabel();
  const [title, setTitle] = useState(currentTitle);
  const [description, setDescription] = useState(currentDescription);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    const trimmedTitle = title.trim();
    const trimmedDesc = description.trim();
    if (!trimmedTitle) {
      setError(t("titleEmpty"));
      return;
    }
    if (trimmedTitle === currentTitle && trimmedDesc === currentDescription) {
      onClose();
      return;
    }
    setSaving(true);
    setError(null);
    const ok = await onSubmit(trimmedTitle, trimmedDesc);
    setSaving(false);
    if (ok) onClose();
    else setError(t("saveFailed"));
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !saving) onClose();
      }}
    >
      <div className="bg-background shadow-xl rounded-xl w-full max-h-[90vh] sm:max-w-xl lg:max-w-3xl p-6 flex flex-col">
        <h3 className="text-base font-semibold mb-4">{t("editTitle", { label: labels.singular })}</h3>
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1" style={{ color: "var(--foreground)" }}>
            {t("titleField")} <span style={{ color: "var(--error)" }}>*</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value.slice(0, WORKSPACE_TITLE_MAX))}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !saving) handleSave();
            }}
            maxLength={WORKSPACE_TITLE_MAX}
            autoFocus
            className="w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2"
            style={{ borderColor: "var(--border)" }}
          />
          <p className="text-xs text-muted-soft text-right mt-1">{title.length}/{WORKSPACE_TITLE_MAX}</p>
        </div>
        <div className="flex flex-col flex-1 min-h-0">
          <label className="block text-sm font-medium mb-1" style={{ color: "var(--foreground)" }}>
            {t("descriptionField")}
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value.slice(0, WORKSPACE_DESCRIPTION_MAX))}
            maxLength={WORKSPACE_DESCRIPTION_MAX}
            rows={8}
            className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none resize-none flex-1 sm:min-h-45 lg:min-h-65"
            style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--foreground)" }}
            placeholder={t("descriptionPlaceholder")}
          />
          <p className="text-xs text-muted-soft text-right mt-1">{description.length}/{WORKSPACE_DESCRIPTION_MAX}</p>
        </div>
        {error && <p className="text-xs text-error mt-2">{error}</p>}
        <div className="flex gap-3 justify-end mt-5">
          <button
            onClick={onClose}
            disabled={saving}
            className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg disabled:opacity-50"
          >
            {t("cancel")}
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm btn-primary rounded-lg disabled:opacity-50"
          >
            {saving ? "..." : t("save")}
          </button>
        </div>
      </div>
    </div>
  );
}
