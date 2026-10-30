"use client";

import { forwardRef } from "react";
import { useTranslations } from "next-intl";
import { landingUrl } from "@/lib/event/routes";
import { POSTER_MM } from "./posterExport";
import { ACCENT, INK, PAPER, PosterHeader, SANS, SOFT, usePosterArt, type PosterArt } from "./PosterSvg";

/** The poster art for the landing page. */
export function useLandingQr(): PosterArt | null {
  return usePosterArt(typeof window === "undefined" ? "" : landingUrl(window.location.origin));
}

interface Props {
  art: PosterArt | null;
  className?: string;
}

/** A5 poster with one large QR code on an accent panel, same header and footer as the stand posters. */
const LandingPoster = forwardRef<SVGSVGElement, Props>(function LandingPoster({ art, className }, ref) {
  const t = useTranslations("eventAdmin.landing");
  const tp = useTranslations("eventAdmin.poster");
  const host = typeof window === "undefined" ? "" : window.location.host;
  return (
    <svg
      ref={ref}
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${POSTER_MM.w} ${POSTER_MM.h}`}
      className={className}
      role="img"
      aria-label={t("headline")}
      data-testid="landing-poster-svg"
    >
      <rect width={POSTER_MM.w} height={POSTER_MM.h} fill={PAPER} />
      <PosterHeader art={art} />
      <text x={74} y={44} textAnchor="middle" fontFamily={SANS} fontSize="12" fontWeight="700" fill={INK}>
        {t("headline")}
      </text>
      <text x={74} y={54} textAnchor="middle" fontFamily={SANS} fontSize="4.8" fontWeight="500" fill={SOFT}>
        {t("scanHint")}
      </text>
      <rect x={19} y={66} width={110} height={110} rx={6} fill={ACCENT} />
      <rect x={27} y={74} width={94} height={94} rx={3} fill={PAPER} />
      {art && <image href={art.qr} x={32} y={79} width={84} height={84} />}
      <text x={74} y={191} textAnchor="middle" fontFamily={SANS} fontSize="7" fontWeight="700" fill={ACCENT}>
        {host}
      </text>
      <rect x={10} y={195} width={128} height={1} fill={ACCENT} />
      <text x={74} y={202.5} textAnchor="middle" fontFamily={SANS} fontSize="4.2" fontWeight="600" fill={ACCENT}>
        {tp("brand")}
      </text>
    </svg>
  );
});

export default LandingPoster;
