"use client";

import EventBlock from "../_components/EventBlock";
import InfoHero from "./_components/InfoHero";
import { HandlingSection, PurposeSection, TeamSection } from "./_components/InfoSections";
import FeatureTiles from "./_components/FeatureTiles";
import InfoFaq from "./_components/InfoFaq";
import PreviewControls from "./_components/PreviewControls";

/** Public page about the pilot, the event block below the hero is admin content and may be hidden. */
export default function MockupInfoPage() {
  return (
    <main className="max-w-5xl mx-auto px-4 py-8 sm:py-12 flex flex-col gap-12 sm:gap-16">
      <InfoHero />
      <EventBlock hintWhenHidden />
      <PurposeSection />
      <FeatureTiles />
      <HandlingSection />
      <TeamSection />
      <InfoFaq />
      <PreviewControls />
    </main>
  );
}
