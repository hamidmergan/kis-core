"use client";

import { useTranslations } from "next-intl";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import EventBlock from "../../../_components/EventBlock";
import EventBlockCard from "./EventBlockCard";
import EventTileEditor from "./EventTileEditor";

/** Settings on top, the real block below so every change shows at once. */
export default function EventPane() {
  const t = useTranslations("mockup.admin.event");
  return (
    <div className="flex flex-col gap-4">
      <EventBlockCard />
      <EventTileEditor />
      <SettingCard title={t("preview")}>
        <div className="mt-4" data-testid="event-preview">
          <EventBlock />
        </div>
      </SettingCard>
    </div>
  );
}
