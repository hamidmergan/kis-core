"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import LandingPoster, { useLandingQr } from "./LandingPoster";
import { PrintShell } from "./PosterPrintSheet";
import { exportPosterPng } from "./posterExport";
import { BTN_SECONDARY } from "./fields";

/** Poster that leads visitors straight to the landing page, with PNG download and the A4 print route. */
export default function LandingPane() {
  const t = useTranslations("eventAdmin.landing");
  const art = useLandingQr();
  const svgRef = useRef<SVGSVGElement>(null);
  const [busy, setBusy] = useState(false);
  const [printing, setPrinting] = useState(false);
  // Stable so the print shell's effect does not restart on every render.
  const done = useCallback(() => setPrinting(false), []);

  const download = async () => {
    if (!svgRef.current) return;
    setBusy(true);
    try {
      await exportPosterPng(svgRef.current, "poster-landing.png");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SettingCard
      title={t("title")}
      description={t("description")}
      control={
        <>
          <button
            type="button"
            onClick={() => setPrinting(true)}
            disabled={!art || printing}
            className={BTN_SECONDARY}
            data-testid="landing-a4"
          >
            {t("a4")}
          </button>
          <button
            type="button"
            onClick={() => void download()}
            disabled={!art || busy}
            className="px-3 py-2 text-sm btn-primary rounded-md whitespace-nowrap disabled:opacity-50"
            data-testid="landing-png"
          >
            {t("png")}
          </button>
        </>
      }
    >
      <div className="mt-4 flex justify-center">
        <LandingPoster ref={svgRef} art={art} className="w-full max-w-xs h-auto rounded-md border border-border shadow-sm" />
      </div>
      {printing && art && (
        <PrintShell ready onDone={done}>
          <div style={{ padding: "10mm" }}>
            <LandingPoster art={art} className="block w-full h-auto" />
          </div>
        </PrintShell>
      )}
    </SettingCard>
  );
}
