"use client";

import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import type { LanguageChoice, Languages } from "../_lib/types";

/** The pill above the page with every language it can be read in, only when there is more than one. */
export function LanguageSwitch({ value, choices, disabled, title, className, onChange }: {
  value: string; choices: LanguageChoice[]; disabled?: boolean; title?: string; className?: string; onChange: (key: string) => void;
}) {
  const t = useTranslations("tools.pages");
  if (choices.length < 2) return null;
  return (
    <span title={title} className={className}>
      <Select<string> size="sm" value={value} onChange={onChange} disabled={disabled} ariaLabel={t("languageSelect")}
        options={choices.map((c) => ({ value: c.key, label: c.label }))} />
    </span>
  );
}

/** The languages of what the owner can read and switch to, the page's own first. */
export function readableOf(l: Languages | null): LanguageChoice[] {
  if (!l) return [];
  return [l.own, ...l.languages.filter((x) => x.state === "done").map(({ key, label }) => ({ key, label }))];
}
