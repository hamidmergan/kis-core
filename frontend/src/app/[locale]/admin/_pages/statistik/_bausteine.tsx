"use client";

/** Building blocks of the statistics pages, own SVG instead of a chart library. */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";

/* ------------------------------------------------------------------ */
/* Rahmen                                                              */
/* ------------------------------------------------------------------ */

export function Ladeanzeige() {
  const t = useTranslations("admin");
  return <p className="text-sm text-muted">{t("loading")}</p>;
}

export function Karte({
  titel,
  hinweis,
  marke,
  children,
}: {
  titel: string;
  hinweis?: string;
  /** A small mark next to the title, such as 'now' for presence. */
  marke?: string;
  children: ReactNode;
}) {
  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="flex items-center gap-2 text-sm font-medium text-foreground">
        {titel}
        {marke && (
          <span className="flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-[0.07em] text-success">
            <span className="h-1.5 w-1.5 rounded-full bg-success motion-safe:animate-pulse" />
            {marke}
          </span>
        )}
      </p>
      {hinweis && <p className="text-xs text-muted mt-1 max-w-2xl">{hinweis}</p>}
      {children}
    </div>
  );
}

export function Kachel({
  titel,
  wert,
  fuss,
}: {
  titel: string;
  wert: number | string;
  fuss?: string;
}) {
  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="text-2xs font-semibold uppercase tracking-[0.07em] text-muted">{titel}</p>
      <p className="text-3xl font-bold tabular-nums tracking-tight mt-1 text-foreground">
        {typeof wert === "number" ? wert.toLocaleString("de-DE") : wert}
      </p>
      {fuss && <p className="text-xs text-muted-soft mt-1">{fuss}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Gemessene Breite                                                    */
/* ------------------------------------------------------------------ */

function useBreite() {
  const rahmen = useRef<HTMLDivElement>(null);
  const [breite, setBreite] = useState(0);
  useEffect(() => {
    const el = rahmen.current;
    if (!el) return;
    const messen = () => setBreite(el.clientWidth);
    messen();
    const beobachter = new ResizeObserver(messen);
    beobachter.observe(el);
    return () => beobachter.disconnect();
  }, []);
  return { rahmen, breite };
}

/** Round cap only at the data end, the baseline stays square. */
function kappe(x: number, y: number, w: number, h: number, r: number, seite: "oben" | "rechts") {
  const rr = Math.max(0, Math.min(r, w / 2, h));
  if (h <= 0.5) return `M${x} ${y + h}h${w}v${-h}h${-w}z`;
  if (seite === "oben")
    return `M${x} ${y + h}V${y + rr}a${rr} ${rr} 0 0 1 ${rr} ${-rr}h${w - 2 * rr}a${rr} ${rr} 0 0 1 ${rr} ${rr}V${y + h}z`;
  return `M${x} ${y}h${w - rr}a${rr} ${rr} 0 0 1 ${rr} ${rr}v${h - 2 * rr}a${rr} ${rr} 0 0 1 ${-rr} ${rr}H${x}z`;
}

function schoenerHoechstwert(v: number) {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  return Math.ceil(v / (p / 2)) * (p / 2);
}

const de = (n: number) => n.toLocaleString("de-DE");

/* ------------------------------------------------------------------ */
/* Saeulen                                                             */
/* ------------------------------------------------------------------ */

export function Saeulen({
  werte,
  hoehe = 200,
}: {
  werte: { label: string; wert: number }[];
  hoehe?: number;
}) {
  const t = useTranslations("admin.statistik");
  const { rahmen, breite } = useBreite();

  const inhalt = () => {
    if (werte.length === 0 || breite === 0) return null;
    const L = 46, R = 8, O = 12, U = 26;
    const pb = breite - L - R, ph = hoehe - O - U;
    const max = schoenerHoechstwert(Math.max(...werte.map((w) => w.wert)));
    const y = (v: number) => O + ph - (v / max) * ph;
    const schritt = pb / werte.length;
    const bw = Math.max(3, Math.min(schritt > 90 ? 70 : 38, schritt - (schritt > 26 ? 8 : 3)));
    const jede = werte.length > 20 ? 4 : werte.length > 12 ? 2 : 1;
    const letzte = werte.length - 1;
    // With small numbers prefer whole steps to duplicate labels.
    const marken = max <= 4
      ? Array.from({ length: max + 1 }, (_, i) => i)
      : [0, 1, 2, 3].map((g) => (max * g) / 3);

    return (
      <svg width={breite} height={hoehe} viewBox={`0 0 ${breite} ${hoehe}`} role="img">
        {marken.map((v, g) => {
          return (
            <g key={g}>
              <line x1={L} x2={breite - R} y1={y(v)} y2={y(v)} className="stroke-border-soft" strokeWidth={1} />
              <text x={L - 8} y={y(v) + 3.5} textAnchor="end" className="fill-muted-soft text-3xs tabular-nums">
                {de(Math.round(v))}
              </text>
            </g>
          );
        })}
        {werte.map((w, i) => {
          const x = L + i * schritt + (schritt - bw) / 2;
          const zeigen = i % jede === 0 || (i === letzte && letzte % jede >= jede / 2);
          return (
            <g key={i}>
              {w.wert > 0 && (
                <path d={kappe(x, y(w.wert), bw, O + ph - y(w.wert), 4, "oben")} className="fill-kb">
                  <title>{`${w.label}: ${de(w.wert)}`}</title>
                </path>
              )}
              {zeigen && (
                <text
                  x={L + i * schritt + schritt / 2}
                  y={hoehe - 8}
                  textAnchor="middle"
                  className="fill-muted-soft text-3xs tabular-nums"
                >
                  {w.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    );
  };

  return (
    <div ref={rahmen} className="mt-4">
      {werte.length === 0 ? (
        <p className="text-xs text-muted-soft">{t("noData")}</p>
      ) : (
        inhalt()
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Liegende Balken                                                     */
/* ------------------------------------------------------------------ */

export interface BalkenZeile {
  label: string;
  wert: number;
  /** An extra number on the right, such as 'finished' next to 'started'. */
  zweite?: number | string;
  /** A custom label instead of the number, such as '84 %'. */
  text?: string;
  /** A custom fill, such as a light to dark gradient for ordered levels. */
  farbe?: string;
}

export function Balken({
  zeilen,
  kopf,
  labelBreite = 168,
}: {
  zeilen: BalkenZeile[];
  /** Headings of the number columns, at most two. */
  kopf?: [string] | [string, string];
  labelBreite?: number;
}) {
  const t = useTranslations("admin.statistik");
  const { rahmen, breite } = useBreite();

  const inhalt = () => {
    if (zeilen.length === 0 || breite === 0) return null;
    const balkenH = 17, luecke = 11, kopfH = kopf ? 20 : 0;
    const zeilenH = balkenH + luecke;
    const spalten = zeilen.some((z) => z.zweite !== undefined) ? 2 : 1;
    const spaltenB = 112;
    const hoehe = zeilen.length * zeilenH + 4 + kopfH;
    const pb = Math.max(40, breite - labelBreite - spaltenB * spalten);
    const max = Math.max(...zeilen.map((z) => z.wert), 1);
    const x = (k: number) => breite - 4 - (spalten - 1 - k) * spaltenB;

    return (
      <svg width={breite} height={hoehe} viewBox={`0 0 ${breite} ${hoehe}`} role="img">
        {kopf?.map((k, i) => (
          <text key={i} x={x(i)} y={11} textAnchor="end" className="fill-muted text-3xs">
            {k}
          </text>
        ))}
        {zeilen.map((z, i) => {
          const y = i * zeilenH + 2 + kopfH;
          const bw = Math.max(2, (z.wert / max) * pb);
          return (
            <g key={i}>
              <text x={0} y={y + balkenH / 2 + 4} className="fill-foreground-soft text-xs">
                {z.label}
              </text>
              {z.wert > 0 && (
                <path
                  d={kappe(labelBreite, y, bw, balkenH, 4, "rechts")}
                  className={z.farbe ?? "fill-kb"}
                >
                  <title>{`${z.label}: ${de(z.wert)}`}</title>
                </path>
              )}
              <text x={x(0)} y={y + balkenH / 2 + 4} textAnchor="end" className="fill-foreground text-xs tabular-nums">
                {z.text ?? de(z.wert)}
              </text>
              {z.zweite !== undefined && (
                <text x={x(1)} y={y + balkenH / 2 + 4} textAnchor="end" className="fill-muted text-xs tabular-nums">
                  {typeof z.zweite === "number" ? de(z.zweite) : z.zweite}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    );
  };

  return (
    <div ref={rahmen} className="mt-4">
      {zeilen.length === 0 ? (
        <p className="text-xs text-muted-soft">{t("noData")}</p>
      ) : (
        inhalt()
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/** A stacked row, for shares of a whole */
/* ------------------------------------------------------------------ */

export function AnteilsZeile({
  teile,
  farben,
}: {
  teile: { label: string; wert: number }[];
  farben: string[];
}) {
  const summe = teile.reduce((s, p) => s + p.wert, 0) || 1;
  return (
    <div className="mt-4">
      <div className="flex gap-0.5 h-6">
        {teile.map((p, i) => (
          <span
            key={i}
            className={`${farben[i]} first:rounded-l-md last:rounded-r-md`}
            style={{ width: `${(p.wert / summe) * 100}%` }}
            title={`${p.label}: ${de(p.wert)}`}
          />
        ))}
      </div>
      <div className="flex gap-4 mt-3 flex-wrap text-xs text-muted">
        {teile.map((p, i) => (
          <span key={i} className="flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-sm ${farben[i]}`} />
            {p.label}
            <span className="tabular-nums text-foreground-soft">
              {Math.round((p.wert / summe) * 100)} %
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}


/* ------------------------------------------------------------------ */
/** Curve with an area, for cumulative values */
/* ------------------------------------------------------------------ */

export function Kurve({
  werte,
  hoehe = 200,
}: {
  werte: { label: string; wert: number }[];
  hoehe?: number;
}) {
  const t = useTranslations("admin.statistik");
  const { rahmen, breite } = useBreite();

  const inhalt = () => {
    if (werte.length < 2 || breite === 0) return null;
    const L = 46, R = 12, O = 12, U = 26;
    const pb = breite - L - R, ph = hoehe - O - U;
    const max = schoenerHoechstwert(Math.max(...werte.map((w) => w.wert)));
    const x = (i: number) => L + (i / (werte.length - 1)) * pb;
    const y = (v: number) => O + ph - (v / max) * ph;
    const linie = werte.map((w, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(w.wert).toFixed(1)}`).join("");
    const letzter = werte[werte.length - 1];
    const marken = max <= 4
      ? Array.from({ length: max + 1 }, (_, i) => i)
      : [0, 1, 2, 3].map((g) => (max * g) / 3);

    return (
      <svg width={breite} height={hoehe} viewBox={`0 0 ${breite} ${hoehe}`} role="img">
        {marken.map((v, g) => (
          <g key={g}>
            <line x1={L} x2={breite - R} y1={y(v)} y2={y(v)} className="stroke-border-soft" strokeWidth={1} />
            <text x={L - 8} y={y(v) + 3.5} textAnchor="end" className="fill-muted-soft text-3xs tabular-nums">
              {de(Math.round(v))}
            </text>
          </g>
        ))}
        <path d={`${linie}L${x(werte.length - 1)} ${O + ph}L${L} ${O + ph}z`} className="fill-kb/12" />
        <path d={linie} fill="none" strokeWidth={2} strokeLinejoin="round" className="stroke-kb" />
        <circle cx={x(werte.length - 1)} cy={y(letzter.wert)} r={4} className="fill-kb" />
        {werte.map((w, i) =>
          i % 4 === 0 || i === werte.length - 1 ? (
            <text key={i} x={x(i)} y={hoehe - 8} textAnchor="middle" className="fill-muted-soft text-3xs tabular-nums">
              {w.label}
            </text>
          ) : null,
        )}
      </svg>
    );
  };

  return (
    <div ref={rahmen} className="mt-4">
      {werte.length < 2 ? <p className="text-xs text-muted-soft">{t("noData")}</p> : inhalt()}
    </div>
  );
}
