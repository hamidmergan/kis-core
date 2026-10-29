"use client";

import { useTranslations } from "next-intl";
import { SettingCard, Switch } from "@/app/[locale]/admin/_settings/fields";
import { useEventConfig } from "@/lib/event/adminStore";
import type { RaffleConfig } from "@/lib/event/types";
import { TextPair } from "./fields";

/** Switch and the four texts of the raffle under a full stamp card. */
export default function RaffleCard() {
  const t = useTranslations("eventAdmin.raffle");
  const [config, update] = useEventConfig();
  const raffle = config.raffle;
  const set = (patch: Partial<RaffleConfig>) => update((c) => ({ ...c, raffle: { ...c.raffle, ...patch } }));

  return (
    <SettingCard
      title={t("title")}
      description={raffle.enabled ? t("active") : t("disabled")}
      control={<Switch checked={raffle.enabled} onChange={(enabled) => set({ enabled })} label={t("toggleAria")} />}
    >
      <div className="mt-4 flex flex-col gap-3" data-testid="raffle-admin">
        <TextPair label={t("heading")} value={raffle.title} onChange={(title) => set({ title })} />
        <TextPair label={t("text")} value={raffle.text} rows={2} onChange={(text) => set({ text })} />
        <TextPair label={t("consent")} value={raffle.consent} rows={3} onChange={(consent) => set({ consent })} />
        <p className="text-xs text-muted -mt-1">{t("consentHint")}</p>
        <TextPair label={t("done")} value={raffle.done} rows={2} onChange={(done) => set({ done })} />
      </div>
    </SettingCard>
  );
}
