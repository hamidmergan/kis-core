"use client";

import { Suspense, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import EventBlock from "@/components/event/EventBlock";
import EventBanner from "@/components/event/EventBanner";
import { usePublicEvent } from "@/lib/event/usePublicEvent";
import HeroRoles from "./_components/landing/HeroRoles";
import InfoHero from "./_components/landing/InfoHero";
import { ContactSection, PurposeSection } from "./_components/landing/InfoSections";
import LearnRows from "./_components/landing/LearnRows";
import ServiceGrid from "./_components/landing/ServiceGrid";
import InfoFaq from "./_components/landing/InfoFaq";
import ScrollTopButton from "./_components/landing/ScrollTopButton";
import { useFitZoom } from "./_components/landing/useFitZoom";

/** Old invitation links still point at "/?code=", the enrolment is handled on the workspace list. */
function CodeForward() {
  const params = useSearchParams();
  const router = useRouter();
  const code = params.get("code");
  useEffect(() => {
    if (code) router.replace(`/workspace?code=${encodeURIComponent(code)}`);
  }, [code, router]);
  return null;
}

function Hero() {
  const params = useSearchParams();
  if (params.get("hero") === "center") return <InfoHero layout="center" />;
  if (params.get("hero") === "plain") return <InfoHero layout="split" />;
  return <HeroRoles />;
}

// Zoom steps by window size, the ranges do not overlap so exactly one wins.
const ZOOM = [
  "[--zoom:1]",
  "[@media(min-width:1024px)_and_(max-width:1279px)_and_(min-height:761px)]:[--zoom:1.25]",
  "[@media(min-width:1280px)_and_(min-height:761px)_and_(max-height:849px)]:[--zoom:1.25]",
  "[@media(min-width:1280px)_and_(min-height:850px)]:[--zoom:1.5]",
  "[@media(min-width:1024px)_and_(max-height:760px)]:[--zoom:1.05]",
].join(" ");

/** Public page about the pilot, built as full-width bands, the event block is admin content and the server hides it outside its period. */
export default function InfoPage() {
  const mainRef = useRef<HTMLElement>(null);
  useFitZoom(mainRef, "info-hero");
  const { data } = usePublicEvent();
  return (
    <>
      {/* Outside the zoomed main so the banner keeps the header's size whatever zoom the hero gets. */}
      <EventBanner block={data?.eventBlock ?? null} />
      {/* Grows like browser zoom on wide screens, breakpoints are container queries so they follow the zoomed width. */}
      <main ref={mainRef} className={`@container [zoom:var(--zoom)] ${ZOOM}`}>
        <Suspense fallback={<HeroRoles />}>
          <CodeForward />
          <Hero />
        </Suspense>
        <EventBlock block={data?.eventBlock ?? null} bleed />
        <PurposeSection />
        <LearnRows />
        <ServiceGrid />
        <InfoFaq />
        <ContactSection />
        <ScrollTopButton />
      </main>
    </>
  );
}
