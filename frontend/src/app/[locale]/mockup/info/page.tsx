"use client";

import EventBlock from "../_components/EventBlock";
import Band from "./_components/Band";
import InfoHero from "./_components/InfoHero";
import { HandlingSection, PurposeSection, TeamSection } from "./_components/InfoSections";
import FeatureTiles from "./_components/FeatureTiles";
import InfoFaq from "./_components/InfoFaq";
import PreviewControls from "./_components/PreviewControls";

/** Public page about the pilot, built as full-width bands, the event block is admin content and may be hidden. */
export default function MockupInfoPage() {
  return (
    <main>
      <InfoHero />
      <Band>
        <EventBlock hintWhenHidden />
      </Band>
      <PurposeSection />
      <FeatureTiles />
      <HandlingSection />
      <TeamSection />
      <InfoFaq />
      <Band>
        <PreviewControls />
      </Band>
    </main>
  );
}
