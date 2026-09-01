"use client";

/** Switch and text of the first-login welcome dialog belong in one card. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useSetting } from "./SettingsProvider";
import { SettingCard, Switch } from "./fields";

export default function WelcomeModalCard() {
  const t = useTranslations("admin.welcomeModalCard");
  const enabled = useSetting<boolean>("welcome_modal_enabled", true);
  const text = useSetting<string>("welcome_modal_text", "");
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
        rows={6}
        placeholder={t("placeholder")}
        aria-label={t("title")}
        className="mt-3 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:border-kb disabled:opacity-50 resize-y"
      />
      <p className="mt-2 text-xs text-muted-soft">{t("hint")}</p>
    </SettingCard>
  );
}
