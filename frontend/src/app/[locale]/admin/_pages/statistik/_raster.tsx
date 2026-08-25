"use client";

/**
 * Das Raster Wochentag mal Stunde.
 *
 * Ein Feld heisst: so viel passiert an einem typischen Montag um zehn. Also ein
 * Durchschnitt und keine Summe, sonst waeren die Zeitraeume nicht vergleichbar,
 * weil "alles" mehr Wochen enthaelt als "30 Tage".
 *
 * Die Farbskala haengt am hoechsten Wert ueber alle Zeitraeume und nicht am
 * gewaehlten. Nur so wird beim Umschalten sichtbar, dass der Betrieb gewachsen
 * ist: waere sie relativ, saehe jeder Zeitraum gleich aus.
 *
 * Die Felder fuellen die Karte statt eine feste Breite zu haben. Ein Raster, das
 * auf halber Strecke aufhoert, sieht aus wie ein Fehler.
 */

import { useTranslations } from "next-intl";
import HoverTooltip from "@/components/ui/HoverTooltip";

const TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

/** Fuenf Stufen aus der Hausfarbe. Deckkraft statt eigener Werte, damit die
 *  Stufen im hellen wie im dunklen Bild ueber dem Kartengrund stimmen. */
const STUFEN = ["bg-kb/10", "bg-kb/30", "bg-kb/50", "bg-kb/75", "bg-kb"];

/** Unter dieser Marke faerbt sich das Raster nicht voll aus.
 *
 *  Ohne sie richtet sich die Skala nach dem hoechsten Wert, den es gerade gibt,
 *  und der ist auf einer ruhigen Anlage eine vier. Dann stuende ein Feld mit vier
 *  Auftraegen im dunkelsten Ton und hiesse "am meisten", obwohl fast nichts los
 *  war. Sobald echter Betrieb laeuft, liegt der Hoechstwert darueber und die
 *  Marke spielt keine Rolle mehr.
 */
const MINDESTSKALA = 20;

export function Raster({
  werte,
  einheit,
  max,
}: {
  werte: number[][];
  einheit: string;
  /** Hoechster Wert ueber alle Zeitraeume, damit die Skala fest bleibt. */
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
            // Der Hinweis kommt aus dem Bestand und nicht aus `title`: dessen
            // Verzoegerung von rund einer Sekunde laesst sich nicht abstellen,
            // und beim Wandern ueber das Raster wartet niemand so lange.
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

/** Die Zeitraum-Knoepfe stehen in der Karte, nicht ueber der Seite: sie wirken
 *  nur auf dieses eine Raster, und eine Leiste, die global aussieht aber fast
 *  nichts tut, ist schlechter als keine. */
export function ZeitraumChips({
  wert,
  setzen,
}: {
  wert: string;
  setzen: (w: string) => void;
}) {
  const t = useTranslations("admin.statistik");
  const auswahl = [
    ["alles", t("range.all")],
    ["jahr", t("range.year")],
    ["30t", t("range.days30")],
  ] as const;

  return (
    <div className="flex gap-1.5 mt-4">
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
