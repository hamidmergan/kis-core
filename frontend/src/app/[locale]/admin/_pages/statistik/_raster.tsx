"use client";

/** The weekday by hour grid, average and a fixed colour scale. */

import { useTranslations } from "next-intl";
import HoverTooltip from "@/components/ui/HoverTooltip";

const TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

/** Five steps from the house colour, via opacity instead of separate values. */
const STUFEN = ["bg-kb/10", "bg-kb/30", "bg-kb/50", "bg-kb/75", "bg-kb"];

/** Below this mark the grid does not fill in completely. */
const MINDESTSKALA = 20;

export function Raster({
  werte,
  einheit,
  max,
}: {
  werte: number[][];
  einheit: string;
  /** Highest value across all periods so the scale stays fixed. */
  max: number;
}) {
  const t = useTranslations("admin.statistik");
  const grenze = Math.max(max, ...werte.flat(), MINDESTSKALA);
  const zeig = (v: number) =>
    v < 10
      ? v.toLocaleString("de-DE", { maximumFractionDigits: 1 })
      : Math.round(v).toLocaleString("de-DE");

  return (
    <div className="mt-4">
      <div className="flex gap-0.5 pl-8 mb-1">
        {Array.from({ length: 24 }, (_, h) => (
          <span
            key={h}
            className="flex-1 min-w-0 text-3xs text-muted-soft tabular-nums text-center"
          >
            {h % 2 === 0 ? String(h).padStart(2, "0") : ""}
          </span>
        ))}
      </div>

      {werte.map((zeile, tag) => (
        <div key={tag} className="flex gap-0.5 items-center mb-0.5">
          <span className="w-8 shrink-0 text-3xs text-muted-soft">{TAGE[tag]}</span>
          {zeile.map((wert, stunde) => (
            // Its own tooltip instead of title, whose delay is too long.
            <HoverTooltip
              key={stunde}
              text={`${TAGE[tag]}, ${String(stunde).padStart(2, "0")}:00\n⌀ ${zeig(wert)} ${einheit}`}
            >
              <span
                className={`flex-1 min-w-0 h-5 rounded-sm ${
                  STUFEN[Math.min(4, Math.floor((wert / grenze) * 5))]
                }`}
              />
            </HoverTooltip>
          ))}
        </div>
      ))}

      <div className="flex items-center gap-2 mt-3 text-2xs text-muted-soft">
        <span>{t("heat.low")}</span>
        <span className="flex gap-0.5">
          {STUFEN.map((s, i) => (
            <span key={i} className={`w-4 h-3 rounded-sm ${s}`} />
          ))}
        </span>
        <span>{t("heat.high")}</span>
      </div>
    </div>
  );
}

/** The period buttons, at the top of a page they scope everything below. */
export function ZeitraumChips({
  wert,
  setzen,
  className = "mt-4",
}: {
  wert: string;
  setzen: (w: string) => void;
  className?: string;
}) {
  const t = useTranslations("admin.statistik");
  const auswahl = [
    ["jahr", t("range.year")],
    ["halbjahr", t("range.halfYear")],
    ["30t", t("range.days30")],
  ] as const;

  return (
    <div className={`flex gap-1.5 ${className}`}>
      {auswahl.map(([k, label]) => (
        <button
          key={k}
          type="button"
          onClick={() => setzen(k)}
          aria-pressed={wert === k}
          className={`px-3 py-1 text-xs rounded-full border transition-colors ${
            wert === k
              ? "bg-kb text-white border-kb font-semibold"
              : "border-border text-foreground-soft hover:border-kb hover:text-kb"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
