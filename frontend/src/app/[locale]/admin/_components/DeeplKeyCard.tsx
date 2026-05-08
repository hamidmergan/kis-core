"use client";

import React, { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

export interface DeeplKeyCardProps {
  overrideSet: boolean;
  overrideLastChars: string | null;
  envLastChars: string | null;
  onChanged: () => void;
}

export default function DeeplKeyCard({
  overrideSet,
  overrideLastChars,
  envLastChars,
  onChanged,
}: DeeplKeyCardProps) {
  const t = useTranslations("admin.settings.deeplKey");

  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    setDraft("");
  }, [overrideSet, overrideLastChars]);

  const submit = async (value: string) => {
    setSaving(true);
    try {
      await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deepl_api_key_override: value }),
      });
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 1500);
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const handleSave = () => {
    const v = draft.trim();
    if (!v) return;
    submit(v);
  };

  const handleClear = () => {
    submit("");
  };

  const status = overrideSet
    ? t("activeOverride", { last: overrideLastChars ?? "" })
    : envLastChars
      ? t("activeEnv", { last: envLastChars })
      : t("activeEnvNoKey");

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="text-sm font-medium text-foreground mb-1">{t("title")}</p>
      <p className="text-xs text-muted-soft mb-4">{t("hint")}</p>

      <div className="flex items-center gap-2">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSave();
          }}
          placeholder={t("placeholderEmpty")}
          disabled={saving}
          spellCheck={false}
          autoComplete="off"
          className="flex-1 font-mono text-xs px-3 py-1.5 border-2 border-border rounded-md hover:border-kb focus:outline-none focus:border-kb disabled:opacity-50"
        />
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !draft.trim()}
          className="btn-primary px-3 py-1.5 text-xs font-medium rounded-md disabled:opacity-40"
        >
          {saving ? t("saving") : savedFlash ? t("saved") : t("save")}
        </button>
        {overrideSet && (
          <button
            type="button"
            onClick={handleClear}
            disabled={saving}
            className="text-xs text-muted hover:text-error px-2 py-1"
          >
            {t("clear")}
          </button>
        )}
      </div>

      <p className="text-xs text-muted mt-2 font-mono">{status}</p>
    </div>
  );
}
