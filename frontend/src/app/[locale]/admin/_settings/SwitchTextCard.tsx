"use client";

/** A switch and its text in one card, shared by welcome dialog and start page notice. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useSetting } from "./SettingsProvider";
import { SettingCard, Switch } from "./fields";

export default function SwitchTextCard({ namespace, enabledKey, enabledDefault, textKey, rows }: {
  namespace: "admin.welcomeModalCard" | "admin.homeNoticeCard";
  enabledKey: string;
  enabledDefault: boolean;
  textKey: string;
  rows: number;
}) {
  const t = useTranslations(namespace);
  const enabled = useSetting<boolean>(enabledKey, enabledDefault);
  const text = useSetting<string>(textKey, "");
  const [draft, setDraft] = useState("");

  useEffect(() => {
    if (text.value !== null) setDraft(text.value);
  }, [text.value]);

  if (enabled.loading) return null;
  const on = enabled.value ?? false;

  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed !== text.value) void text.set(trimmed);
  };

  return (
    <SettingCard
      title={t("title")}
      description={on ? t("active") : t("disabled")}
      error={enabled.error ?? text.error}
      control={
        <Switch
          checked={on}
          onChange={(n) => void enabled.set(n)}
          disabled={enabled.saving}
          label={t("toggleAria")}
        />
      }
    >
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        disabled={text.saving}
        rows={rows}
        placeholder={t("placeholder")}
        aria-label={t("title")}
        className="mt-3 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:border-kb disabled:opacity-50 resize-y"
      />
      <p className="mt-2 text-xs text-muted-soft">{t("hint")}</p>
    </SettingCard>
  );
}
