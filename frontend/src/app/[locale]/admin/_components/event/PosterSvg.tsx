"use client";

import { forwardRef, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import QRCode from "qrcode";
import { useEventConfig } from "@/lib/event/adminStore";
import { EVENT_ICONS } from "@/lib/event/icons";
import { stationQrUrl } from "@/lib/event/routes";
import { useText2 } from "@/lib/event/useText2";
import type { Station } from "@/lib/event/types";
import { KIS_LOGO_MARKUP, KIS_LOGO_VIEWBOX } from "./kisLogo";
import { POSTER_MM } from "./posterExport";

export const ACCENT = "#004261";
export const INK = "#1b2a33";
export const SOFT = "#5a6b75";
export const PAPER = "#ffffff";
export const SANS = "system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
export const MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";

export interface PosterArt {
  qr: string;
  thl: string;
  isy: string;
  francis: string;
}

const LOGO_FILES = {
  thl: "/logos/logo-thl.jpg",
  isy: "/logos/isy-logo.png",
  francis: "/logos/ask-francis-logo-transparent-black.svg",
} as const;
let logoCache: Promise<Pick<PosterArt, "thl" | "isy" | "francis">> | null = null;

function toDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/** The partner logos as data URLs, a poster SVG with outside image links would come out blank in PNG export. */
function loadLogos(): Promise<Pick<PosterArt, "thl" | "isy" | "francis">> {
  logoCache ??= Promise.all(
    Object.values(LOGO_FILES).map((src) => fetch(src).then((r) => r.blob()).then(toDataUrl)),
  )
    .then(([thl, isy, francis]) => ({ thl, isy, francis }))
    .catch((e) => {
      logoCache = null;
      throw e;
    });
  return logoCache;
}

/** QR for any target plus the logos as data URLs so the SVG stays self-contained for PNG export and print, null until all are ready. */
export function usePosterArt(target: string): PosterArt | null {
  const [art, setArt] = useState<PosterArt | null>(null);
  useEffect(() => {
    if (!target) return;
    let active = true;
    Promise.all([QRCode.toDataURL(target, { width: 512, margin: 0, color: { dark: INK, light: PAPER } }), loadLogos()])
      .then(([qr, logos]) => { if (active) setArt({ qr, ...logos }); })
      .catch(() => { if (active) setArt(null); });
    return () => { active = false; };
  }, [target]);
  return art;
}

/** The poster art for one stand. */
export function useStationQr(stationId: string): PosterArt | null {
  return usePosterArt(typeof window === "undefined" ? "" : stationQrUrl(window.location.origin, stationId));
}

export const LOGO_H = 8;
export const LOGO_W = (LOGO_H * KIS_LOGO_VIEWBOX.w) / KIS_LOGO_VIEWBOX.h;
// White plate on the right of the bar, the partner logos have white backgrounds of their own.
export const LOGO_IMG_H = 7;
export const PLATE_PAD = 2;
export const THL_W = (LOGO_IMG_H * 473) / 166;
export const ISY_W = (LOGO_IMG_H * 634) / 523;
export const PLATE_W = PLATE_PAD * 3 + THL_W + ISY_W;
const KIS_H = 6;
const KIS_W = (KIS_H * KIS_LOGO_VIEWBOX.w) / KIS_LOGO_VIEWBOX.h;
// Same width as the old logo with bird, the flatter wordmark gets the height that follows from it.
const FRANCIS_W = (6 * 124.86) / 24;
const FRANCIS_H = (FRANCIS_W * 13.36) / 98.4;
// Two white plates on the accent bar: askFrancis on the left, KIS, THL and ISy side by side on the right.
// Space between plate edge and logo, wider than the gap between logos.
const EDGE_PAD = 4;
const RIGHT_PLATE_W = EDGE_PAD * 2 + PLATE_PAD * 2 + KIS_W + THL_W + ISY_W;
const BAR_EDGE = 2;
const BAR_H = 16;
const PLATE_Y = 2;
const PLATE_H = BAR_H - PLATE_Y * 2;
const RIGHT_PLATE_X = POSTER_MM.w - BAR_EDGE - RIGHT_PLATE_W;
const logoY = (h: number) => PLATE_Y + (PLATE_H - h) / 2;

/** The accent bar at the top of every poster. */
export function PosterHeader({ art }: { art: PosterArt | null }) {
  return (
    <>
      <rect width={POSTER_MM.w} height={BAR_H} fill={ACCENT} />
      {art && (
        <>
          <rect x={BAR_EDGE} y={PLATE_Y} width={FRANCIS_W + EDGE_PAD * 2} height={PLATE_H} rx={1.5} fill={PAPER} />
          <image href={art.francis} x={BAR_EDGE + EDGE_PAD} y={logoY(FRANCIS_H)} width={FRANCIS_W} height={FRANCIS_H} />
          <rect x={RIGHT_PLATE_X} y={PLATE_Y} width={RIGHT_PLATE_W} height={PLATE_H} rx={1.5} fill={PAPER} />
          <svg
            x={RIGHT_PLATE_X + EDGE_PAD}
            y={logoY(KIS_H)}
            width={KIS_W}
            height={KIS_H}
            viewBox={`${KIS_LOGO_VIEWBOX.x} ${KIS_LOGO_VIEWBOX.y} ${KIS_LOGO_VIEWBOX.w} ${KIS_LOGO_VIEWBOX.h}`}
            dangerouslySetInnerHTML={{ __html: KIS_LOGO_MARKUP }}
          />
          <image href={art.thl} x={RIGHT_PLATE_X + EDGE_PAD + PLATE_PAD + KIS_W} y={logoY(LOGO_IMG_H)} width={THL_W} height={LOGO_IMG_H} />
          <image href={art.isy} x={RIGHT_PLATE_X + EDGE_PAD + PLATE_PAD * 2 + KIS_W + THL_W} y={logoY(LOGO_IMG_H)} width={ISY_W} height={LOGO_IMG_H} />
        </>
      )}
    </>
  );
}

export function nameLines(name: string): string[] {
  if (name.length <= 18) return [name];
  const words = name.split(" ");
  let first = "";
  while (words.length && (first + " " + words[0]).trim().length <= 18) first = (first + " " + words.shift()).trim();
  return first ? [first, words.join(" ")] : [name];
}

interface Props {
  station: Station;
  art: PosterArt | null;
  className?: string;
}

const PosterSvg = forwardRef<SVGSVGElement, Props>(function PosterSvg({ station, art, className }, ref) {
  const t = useTranslations("eventAdmin.poster");
  const [config] = useEventConfig();
  const showCode = !config.hideCodeOnPosters;
  const text = useText2();
  const Icon = EVENT_ICONS[station.icon];
  const lines = nameLines(text(station.name));
  const subtitle = text(station.blurb).trim();
  const nameY = subtitle ? (lines.length > 1 ? 62 : 67) : (lines.length > 1 ? 68 : 72);
  const subtitleY = nameY + (lines.length - 1) * 10 + 8;
  return (
    <svg
      ref={ref}
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${POSTER_MM.w} ${POSTER_MM.h}`}
      className={className}
      role="img"
      aria-label={text(station.name)}
      data-testid="poster-svg"
    >
      <rect width={POSTER_MM.w} height={POSTER_MM.h} fill={PAPER} />
      <PosterHeader art={art} />
      <circle cx={74} cy={36} r={15} fill={ACCENT} />
      <Icon x={63} y={25} width={22} height={22} color={PAPER} weight="bold" />
      {lines.map((line, i) => (
        <text
          key={i}
          x={74}
          y={nameY + i * 10}
          textAnchor="middle"
          fontFamily={SANS}
          fontSize="9"
          fontWeight="700"
          fill={INK}
        >
          {line}
        </text>
      ))}
      {subtitle && (
        <text x={74} y={subtitleY} textAnchor="middle" fontFamily={SANS} fontSize="4.6" fontWeight="500" fill={SOFT}>
          {subtitle}
        </text>
      )}
      <rect x={38} y={84} width={72} height={72} rx={3} fill={PAPER} stroke={ACCENT} strokeWidth={0.6} />
      {art && <image href={art.qr} x={42} y={88} width={64} height={64} />}
      <text x={74} y={167} textAnchor="middle" fontFamily={SANS} fontSize="5.4" fill={SOFT}>
        {t(showCode ? "scanHint" : "scanHintOnly")}
      </text>
      {showCode && (
        <text
          x={74}
          y={192}
          textAnchor="middle"
          fontFamily={MONO}
          fontSize="19"
          fontWeight="700"
          fill={ACCENT}
          letterSpacing="2.5"
        >
          {station.code}
        </text>
      )}
      <rect x={10} y={195} width={128} height={1} fill={ACCENT} />
      <text x={74} y={202.5} textAnchor="middle" fontFamily={SANS} fontSize="4.2" fontWeight="600" fill={ACCENT}>
        {t("brand")}
      </text>
    </svg>
  );
});

export default PosterSvg;
