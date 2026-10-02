"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import EventBlock from "../_components/EventBlock";
import InfoHero from "./_components/InfoHero";
import { HandlingSection, PurposeSection, TeamSection } from "./_components/InfoSections";
import FeatureTiles from "./_components/FeatureTiles";
import InfoFaq from "./_components/InfoFaq";

function Hero() {
  const params = useSearchParams();
  return <InfoHero layout={params.get("hero") === "center" ? "center" : "split"} />;
}

/** Public page about the pilot, built as full-width bands, the event block is admin content and may be hidden. */
export default function MockupInfoPage() {
  return (
    <main>
      <Suspense fallback={<InfoHero />}>
        <Hero />
      </Suspense>
      <EventBlock bleed />
      <PurposeSection />
      <FeatureTiles />
      <HandlingSection />
      <TeamSection />
      <InfoFaq />
    </main>
  );
}
