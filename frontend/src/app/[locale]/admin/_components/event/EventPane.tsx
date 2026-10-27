"use client";

import { useTranslations } from "next-intl";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import EventBanner from "@/components/event/EventBanner";
import EventBlock from "@/components/event/EventBlock";
import { useEventConfig } from "@/lib/event/adminStore";
import { eventActive } from "@/lib/event/eventWindow";
import EventBlockCard from "./EventBlockCard";
import EventTileEditor from "./EventTileEditor";

/** Settings on top, the real block below so every change shows at once. */
export default function EventPane() {
  const t = useTranslations("eventAdmin.event");
  const [config] = useEventConfig();
  return (
    <div className="flex flex-col gap-4">
      <EventBlockCard />
      <EventTileEditor />
      <SettingCard title={t("preview")}>
        <div className="mt-4 flex flex-col gap-4" data-testid="event-preview">
          <EventBanner block={eventActive(config.eventBlock) ? config.eventBlock : null} />
          <EventBlock block={eventActive(config.eventBlock) ? config.eventBlock : null} />
        </div>
      </SettingCard>
    </div>
  );
}
