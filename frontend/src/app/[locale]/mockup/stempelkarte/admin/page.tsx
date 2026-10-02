"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import Tabs from "@/components/ui/Tabs";
import StationsPane from "./_components/StationsPane";
import EventPane from "./_components/EventPane";
import StatsCard from "./_components/StatsCard";

type Tab = "stations" | "event" | "stats";
const TABS: Tab[] = ["stations", "event", "stats"];

/** Admin for the stamp card mockup, same head and cards as the real admin area. */
export default function MockupAdminPage() {
  const t = useTranslations("mockup.admin");
  const [tab, setTab] = useState<Tab>("stations");
  return (
    <main className="px-4 py-6 md:px-8 md:py-8 lg:px-10 print:hidden">
      <div className="max-w-5xl mx-auto">
        <p className="hidden md:block text-2xs font-semibold uppercase tracking-[0.09em] text-muted mb-1">{t("eyebrow")}</p>
        <h2 className="text-lg font-semibold">{t("title")}</h2>
        <p className="text-xs text-muted mt-1 mb-6 max-w-2xl">{t("sub")}</p>
        <Tabs<Tab>
          items={TABS.map((key) => ({ key, label: t(`tabs.${key}`) }))}
          active={tab}
          onChange={setTab}
          className="mb-6"
        />
        {tab === "stations" && <StationsPane />}
        {tab === "event" && <EventPane />}
        {tab === "stats" && <StatsCard />}
      </div>
    </main>
  );
}
