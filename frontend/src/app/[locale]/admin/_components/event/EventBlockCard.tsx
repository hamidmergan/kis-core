"use client";

import { useTranslations } from "next-intl";
import { SettingCard, Switch } from "@/app/[locale]/admin/_settings/fields";
import { useEventConfig } from "@/lib/event/adminStore";
import type { EventBlock } from "@/lib/event/types";
import { INPUT, Labeled, TextPair } from "./fields";

/** Switch, period and texts of the event block in one card. */
export default function EventBlockCard() {
  const t = useTranslations("eventAdmin.event");
  const [config, update] = useEventConfig();
  const block = config.eventBlock;
  const set = (patch: Partial<EventBlock>) => update((c) => ({ ...c, eventBlock: { ...c.eventBlock, ...patch } }));

  return (
    <SettingCard
      title={t("title")}
      description={block.enabled ? t("active") : t("disabled")}
      control={<Switch checked={block.enabled} onChange={(enabled) => set({ enabled })} label={t("toggleAria")} />}
    >
      <div className="mt-4 flex flex-col gap-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <Labeled label={t("from")}>
            <input type="date" value={block.from} onChange={(e) => set({ from: e.target.value })} className={`${INPUT} min-w-0`} />
          </Labeled>
          <Labeled label={t("until")}>
            <input type="date" value={block.until} onChange={(e) => set({ until: e.target.value })} className={`${INPUT} min-w-0`} />
          </Labeled>
        </div>
        <TextPair label={t("heading")} value={block.heading} onChange={(heading) => set({ heading })} />
        <TextPair label={t("text")} value={block.text} rows={2} onChange={(text) => set({ text })} />
      </div>
    </SettingCard>
  );
}
