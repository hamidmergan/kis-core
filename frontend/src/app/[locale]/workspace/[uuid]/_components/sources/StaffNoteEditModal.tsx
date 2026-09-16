"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Trash, X } from "@phosphor-icons/react";
import type { StaffNoteLink } from "../../_types";

const MAX_TEXT_LENGTH = 2000;
const MAX_LINKS = 30;
const MAX_LABEL_LENGTH = 100;
const URL_PATTERN = /^(https?:\/\/|mailto:)/i;

interface StaffNoteEditModalProps {
  open: boolean;
  initialText: string | null | undefined;
  initialLinks: StaffNoteLink[];
  onClose: () => void;
  onSave: (text: string | null, links: StaffNoteLink[]) => Promise<void>;
}

interface DraftLink {
  url: string;
  label: string;
}

export function StaffNoteEditModal({ open, initialText, initialLinks, onClose, onSave }: StaffNoteEditModalProps) {
  const t = useTranslations("workspace.detail.sources.staffNote");
  const [text, setText] = useState("");
  const [links, setLinks] = useState<DraftLink[]>([]);
  const [errors, setErrors] = useState<Record<number, { url?: string; label?: string }>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setText(initialText ?? "");
    setLinks(initialLinks.map((l) => ({ url: l.url, label: l.label })));
    setErrors({});
    setSaveError(null);
  }, [open, initialText, initialLinks]);

  if (!open) return null;

  function addLink() {
    if (links.length >= MAX_LINKS) return;
    setLinks((prev) => [...prev, { url: "", label: "" }]);
  }

  function updateLink(index: number, patch: Partial<DraftLink>) {
    setLinks((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));
    setErrors((prev) => {
      const next = { ...prev };
      if (next[index]) {
        const { ...rest } = next[index];
        if (patch.url !== undefined) delete rest.url;
        if (patch.label !== undefined) delete rest.label;
        if (Object.keys(rest).length === 0) delete next[index];
        else next[index] = rest;
      }
      return next;
    });
  }

  function removeLink(index: number) {
    setLinks((prev) => prev.filter((_, i) => i !== index));
    setErrors((prev) => {
      const next: Record<number, { url?: string; label?: string }> = {};
      Object.entries(prev).forEach(([k, v]) => {
        const ki = Number(k);
        if (ki < index) next[ki] = v;
        else if (ki > index) next[ki - 1] = v;
      });
      return next;
    });
  }

  async function handleSave() {
    const trimmedText = text.trim();
    const cleanedLinks: StaffNoteLink[] = [];
    const newErrors: Record<number, { url?: string; label?: string }> = {};

    links.forEach((link, i) => {
      const url = link.url.trim();
      const label = link.label.trim();
      if (!url && !label) return;
      const entryErrors: { url?: string; label?: string } = {};
      if (!URL_PATTERN.test(url)) entryErrors.url = t("linkUrlInvalid");
      if (!label) entryErrors.label = t("linkLabelMissing");
      if (Object.keys(entryErrors).length > 0) {
        newErrors[i] = entryErrors;
      } else {
        cleanedLinks.push({ url, label });
      }
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setSaving(true);
    setSaveError(null);
    try {
      await onSave(trimmedText ? trimmedText : null, cleanedLinks);
      onClose();
    } catch {
      setSaveError(t("saveError"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div
        className="bg-background rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] flex flex-col"
        style={{ backgroundColor: "var(--background)" }}
      >
        <div
          className="flex items-start justify-between px-6 py-4 flex-shrink-0"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <div className="min-w-0">
            <h3 className="text-base font-semibold" style={{ color: "var(--foreground)" }}>
              {t("modalTitle")}
            </h3>
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
              {t("modalSubtitle", { label: "Workspace" })}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("cancel")}
            className="w-7 h-7 flex-shrink-0 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}
          >
            <X size={13} weight="bold" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
          <div>
            <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
              {t("textLabel")}
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value.slice(0, MAX_TEXT_LENGTH))}
              placeholder={t("textPlaceholder")}
              rows={5}
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 resize-y"
              style={{
                backgroundColor: "var(--background)",
                borderColor: "var(--border)",
                color: "var(--foreground)",
              }}
            />
            <p className="mt-1 text-xs text-right" style={{ color: "var(--muted)" }}>
              {t("charCount", { used: text.length, max: MAX_TEXT_LENGTH })}
            </p>
          </div>

          <div>
            <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
              {t("linksLabel")}
            </label>
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
              {t("linksHint")}
            </p>

            <ul className="mt-2 space-y-2">
              {links.map((link, i) => (
                <li key={i} className="flex flex-col gap-1 rounded-lg p-2" style={{ backgroundColor: "var(--surface-dim)" }}>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={link.label}
                      onChange={(e) => updateLink(i, { label: e.target.value.slice(0, MAX_LABEL_LENGTH) })}
                      placeholder={t("linkLabelPlaceholder")}
                      className="flex-1 rounded-md border px-2 py-1.5 text-sm focus:outline-none"
                      style={{
                        backgroundColor: "var(--background)",
                        borderColor: errors[i]?.label ? "var(--error)" : "var(--border)",
                        color: "var(--foreground)",
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => removeLink(i)}
                      aria-label={t("removeLink")}
                      title={t("removeLink")}
                      className="w-7 h-7 flex-shrink-0 flex items-center justify-center rounded-full btn-icon"
                      style={{ backgroundColor: "var(--background)", color: "rgb(185, 28, 28)" }}
                    >
                      <Trash size={13} weight="bold" />
                    </button>
                  </div>
                  <input
                    type="text"
                    value={link.url}
                    onChange={(e) => updateLink(i, { url: e.target.value.slice(0, 500) })}
                    placeholder={t("linkUrlPlaceholder")}
                    className="w-full rounded-md border px-2 py-1.5 text-sm focus:outline-none font-mono"
                    style={{
                      backgroundColor: "var(--background)",
                      borderColor: errors[i]?.url ? "var(--error)" : "var(--border)",
                      color: "var(--foreground)",
                    }}
                  />
                  {(errors[i]?.url || errors[i]?.label) && (
                    <p className="text-xs" style={{ color: "var(--error)" }}>
                      {errors[i]?.url ?? errors[i]?.label}
                    </p>
                  )}
                </li>
              ))}
            </ul>

            {links.length < MAX_LINKS && (
              <button
                type="button"
                onClick={addLink}
                className="mt-2 w-full flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium border-2 border-dashed transition-colors"
                style={{
                  color: "var(--accent)",
                  borderColor: "rgba(0, 66, 97, 0.3)",
                  backgroundColor: "rgba(0, 66, 97, 0.04)",
                }}
              >
                <Plus size={13} weight="bold" />
                {t("addLink")}
              </button>
            )}
          </div>

          {saveError && (
            <p className="text-sm" style={{ color: "var(--error)" }}>{saveError}</p>
          )}
        </div>

        <div
          className="flex gap-3 justify-end px-6 py-4 flex-shrink-0"
          style={{ borderTop: "1px solid var(--border)" }}
        >
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm btn-primary rounded-lg disabled:opacity-50"
          >
            {saving ? t("saving") : t("save")}
          </button>
        </div>
      </div>
    </div>
  );
}
