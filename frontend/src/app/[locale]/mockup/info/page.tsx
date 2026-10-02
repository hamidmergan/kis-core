"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import EventBlock from "../_components/EventBlock";
import HeroTabs from "./_components/HeroTabs";
import InfoHero from "./_components/InfoHero";
import { ContactSection, PurposeSection } from "./_components/InfoSections";
import LearnRows from "./_components/LearnRows";
import ServiceGrid from "./_components/ServiceGrid";
import InfoFaq from "./_components/InfoFaq";

function Hero() {
  const params = useSearchParams();
  if (params.get("hero") === "center") return <InfoHero layout="center" />;
  if (params.get("hero") === "plain") return <InfoHero layout="split" />;
  return <HeroTabs />;
}

// Zoom steps by window size, the ranges do not overlap so exactly one wins.
const ZOOM = [
  "[--zoom:1]",
  "[@media(min-width:1024px)_and_(max-width:1279px)_and_(min-height:761px)]:[--zoom:1.25]",
  "[@media(min-width:1280px)_and_(min-height:761px)_and_(max-height:849px)]:[--zoom:1.25]",
  "[@media(min-width:1280px)_and_(min-height:850px)]:[--zoom:1.5]",
  "[@media(min-width:1024px)_and_(max-height:760px)]:[--zoom:1.05]",
].join(" ");

/** Public page about the pilot, built as full-width bands, the event block is admin content and may be hidden. */
export default function MockupInfoPage() {
  return (
    // Grows like browser zoom on wide screens, breakpoints are container queries so they follow the zoomed width.
    <main className={`@container [zoom:var(--zoom)] ${ZOOM}`}>
      <Suspense fallback={<HeroTabs />}>
        <Hero />
      </Suspense>
      <EventBlock bleed />
      <PurposeSection />
      <LearnRows />
      <ServiceGrid />
      <InfoFaq />
      <ContactSection />
    </main>
  );
}
