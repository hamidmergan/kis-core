"use client";

import { forwardRef, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import QRCode from "qrcode";
import { EVENT_ICONS } from "@/lib/event/icons";
import { stationQrUrl } from "@/lib/event/routes";
import { useText2 } from "@/lib/event/useText2";
import type { Station } from "@/lib/event/types";
import { POSTER_MM } from "./posterExport";

const ACCENT = "#004261";
const INK = "#1b2a33";
const SOFT = "#5a6b75";
const PAPER = "#ffffff";
const SANS = "system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
const MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";

/** QR as a data URL so the SVG stays self-contained for PNG export and print. */
export function useStationQr(stationId: string): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    const target = stationQrUrl(window.location.origin, stationId);
    QRCode.toDataURL(target, { width: 512, margin: 0, color: { dark: INK, light: PAPER } })
      .then((u) => { if (active) setUrl(u); })
      .catch(() => { if (active) setUrl(null); });
    return () => { active = false; };
  }, [stationId]);
  return url;
}

function nameLines(name: string): string[] {
  if (name.length <= 18) return [name];
  const words = name.split(" ");
  let first = "";
  while (words.length && (first + " " + words[0]).trim().length <= 18) first = (first + " " + words.shift()).trim();
  return first ? [first, words.join(" ")] : [name];
}

interface Props {
  station: Station;
  qr: string | null;
  className?: string;
}

const PosterSvg = forwardRef<SVGSVGElement, Props>(function PosterSvg({ station, qr, className }, ref) {
  const t = useTranslations("eventAdmin.poster");
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
      <text x={10} y={10.6} fontFamily={SANS} fontSize="5" fontWeight="600" fill={PAPER} letterSpacing="0.3">
        {t("kicker")}
      </text>
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
      {qr && <image href={qr} x={42} y={88} width={64} height={64} />}
      <text x={74} y={167} textAnchor="middle" fontFamily={SANS} fontSize="5.4" fill={SOFT}>
        {t("scanHint")}
      </text>
      <text x={74} y={178} textAnchor="middle" fontFamily={SANS} fontSize="4.2" fill={SOFT} letterSpacing="0.8">
        {t("codeLabel").toUpperCase()}
      </text>
      <text
        x={74}
        y={196}
        textAnchor="middle"
        fontFamily={MONO}
        fontSize="19"
        fontWeight="700"
        fill={ACCENT}
        letterSpacing="2.5"
      >
        {station.code}
      </text>
      <rect x={10} y={203} width={128} height={1} fill={ACCENT} />
    </svg>
  );
});

export default PosterSvg;
