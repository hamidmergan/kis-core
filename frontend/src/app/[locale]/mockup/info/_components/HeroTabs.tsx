"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import Tabs from "@/components/ui/Tabs";
import Band from "./Band";
import Screenshot from "./Screenshot";
import { useBandTop } from "./useBandTop";

type Key = "aia" | "services";

const H1 = "font-semibold tracking-[-0.02em] leading-[1.05] text-kb!";
const FADE = "col-start-1 row-start-1 transition-opacity duration-300 motion-reduce:transition-none";

/** Hero with two tabs, the assistant and the services, a click swaps headline, sentence and picture. */
export default function HeroTabs() {
  const t = useTranslations("mockup.info");
  const [tab, setTab] = useState<Key>("aia");
  useBandTop("info-hero");
  const copy: Record<Key, { title: string; lead: string; image: string; alt: string; label?: string }> = {
    aia: { title: t("title"), lead: t("lead"), image: "workspace", alt: t("heroAlt") },
    services: { title: t("servicesTitle"), lead: t("servicesLead"), image: "services", alt: t("servicesAlt"), label: t("servicesLabel") },
  };
  const keys: Key[] = ["aia", "services"];
  return (
    <Band tone="hero" testId="info-hero" fill>
      <div className="grid grid-cols-1 @min-[48rem]:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] @min-[80rem]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-10 @min-[64rem]:gap-20 @min-[80rem]:gap-12 items-center">
        <div className="flex flex-col gap-8">
          <Tabs
            variant="underline"
            active={tab}
            onChange={setTab}
            className="self-start"
            items={[
              { key: "aia", label: t("tabAia") },
              { key: "services", label: t("tabServices") },
            ]}
          />
          <div className="grid">
            {keys.map((k) => (
              <div
                key={k}
                className={`${FADE} flex flex-col gap-6 ${tab === k ? "opacity-100" : "opacity-0 pointer-events-none"}`}
                aria-hidden={tab !== k}
              >
                <h1 className={`${H1} text-4xl @min-[40rem]:text-5xl @min-[64rem]:text-6xl @min-[80rem]:text-7xl @min-[96rem]:text-8xl text-balance`}>
                  {copy[k].title}
                </h1>
                <p className="text-lg @min-[40rem]:text-xl @min-[80rem]:text-2xl leading-relaxed text-foreground-soft max-w-2xl text-balance">
                  {copy[k].lead}
                </p>
              </div>
            ))}
          </div>
        </div>
        <div className="grid">
          {keys.map((k) => (
            <div key={k} className={`${FADE} ${tab === k ? "opacity-100" : "opacity-0 pointer-events-none"}`} aria-hidden={tab !== k}>
              <Screenshot name={copy[k].image} alt={copy[k].alt} title={copy[k].label} />
            </div>
          ))}
        </div>
      </div>
    </Band>
  );
}
