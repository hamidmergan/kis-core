"use client";

import { useTranslations } from "next-intl";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import { useEventConfig } from "@/lib/event/adminStore";
import type { CardTexts } from "@/lib/event/types";
import { TextPair } from "./fields";

/** Name, intro and closing words of the stamp card page in both languages. */
export default function CardTextsCard() {
  const t = useTranslations("eventAdmin.cardTexts");
  const [config, update] = useEventConfig();
  const texts = config.cardTexts;
  const set = (patch: Partial<CardTexts>) => update((c) => ({ ...c, cardTexts: { ...c.cardTexts, ...patch } }));

  return (
    <SettingCard title={t("title")} description={t("description")}>
      <div className="mt-4 flex flex-col gap-3" data-testid="card-texts-admin">
        <TextPair label={t("name")} value={texts.title} onChange={(title) => set({ title })} />
        <TextPair label={t("intro")} value={texts.intro} rows={2} onChange={(intro) => set({ intro })} />
        <TextPair label={t("completeTitle")} value={texts.completeTitle} onChange={(completeTitle) => set({ completeTitle })} />
        <TextPair label={t("completeText")} value={texts.completeText} rows={2} onChange={(completeText) => set({ completeText })} />
      </div>
    </SettingCard>
  );
}
