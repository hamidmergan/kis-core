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
}

const LOGO_FILES = { thl: "/logos/logo-thl.jpg", isy: "/logos/isy-logo.png" } as const;
let logoCache: Promise<Pick<PosterArt, "thl" | "isy">> | null = null;

function toDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/** The partner logos as data URLs, a poster SVG with outside image links would come out blank in PNG export. */
function loadLogos(): Promise<Pick<PosterArt, "thl" | "isy">> {
  logoCache ??= Promise.all(
    Object.values(LOGO_FILES).map((src) => fetch(src).then((r) => r.blob()).then(toDataUrl)),
  )
    .then(([thl, isy]) => ({ thl, isy }))
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
  const nameY = lines.length > 1 ? 68 : 72;
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
      <rect width={POSTER_MM.w} height={16} fill={ACCENT} />
      <svg
        x={10}
        y={4}
        width={LOGO_W}
        height={LOGO_H}
        viewBox={`${KIS_LOGO_VIEWBOX.x} ${KIS_LOGO_VIEWBOX.y} ${KIS_LOGO_VIEWBOX.w} ${KIS_LOGO_VIEWBOX.h}`}
        dangerouslySetInnerHTML={{ __html: KIS_LOGO_MARKUP }}
      />
      <text x={10 + LOGO_W + 3} y={10.6} fontFamily={SANS} fontSize="5" fontWeight="600" fill={PAPER} letterSpacing="0.3">
        {t("kicker")}
      </text>
      {art && (
        <>
          <rect x={POSTER_MM.w - 10 - PLATE_W} y={2} width={PLATE_W} height={12} rx={1.5} fill={PAPER} />
          <image href={art.thl} x={POSTER_MM.w - 10 - PLATE_W + PLATE_PAD} y={4.5} width={THL_W} height={LOGO_IMG_H} />
          <image href={art.isy} x={POSTER_MM.w - 10 - PLATE_W + PLATE_PAD + THL_W + PLATE_PAD} y={4.5} width={ISY_W} height={LOGO_IMG_H} />
        </>
      )}
      <circle cx={74} cy={42} r={15} fill={ACCENT} />
      <Icon x={63} y={31} width={22} height={22} color={PAPER} weight="bold" />
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
      <rect x={10} y={203} width={128} height={1} fill={ACCENT} />
    </svg>
  );
});

export default PosterSvg;
