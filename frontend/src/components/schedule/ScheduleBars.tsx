"use client";

import type { Segment } from "./_ranges";

/** Hoehe eines Balkens. */
export const BAR_HEIGHT = 18;
/** Ein einziger Abstand fuer alles: unter der Zahl, zwischen den Balken, ueber der Kachel.
 *  Muss zur Raster-Luecke gap-1 der Balkenebene passen. */
export const BAR_GAP = 4;
/** Innenabstand 4 plus Tageszahl 17, die Zelle hat keinen Rahmen mehr. */
const NUMBER_BLOCK = 21;
/** Einzug am echten Anfang und Ende, damit der Balken dort steht wie eine Kachel.
 *  Entspricht dem seitlichen Innenabstand der Zelle (px-1.5). */
const BAR_INSET = 6;
/** Rundung wie bei den Tages-Kacheln (rounded = 4px). */
const BAR_RADIUS = 4;
/** Der erste Balken faengt genau einen Abstand unter der Tageszahl an. */
export const BAR_TOP = NUMBER_BLOCK + BAR_GAP;

/** Platzhalter unter der Zahl, damit die Kachel genau einen Abstand unter dem
 *  letzten Balken anfaengt. Ein Balken belegt Hoehe plus einen Abstand. */
export function barsSpace(lanes: number): number {
  return lanes === 0 ? 0 : BAR_GAP + lanes * (BAR_HEIGHT + BAR_GAP);
}

/** Ohne Raster-Luecke muss der Abstand zwischen den Spuren am Balken haengen. */
export const BAR_ROW = BAR_HEIGHT + BAR_GAP;

export default function ScheduleBars({ segments }: { segments: Segment[] }) {
  if (segments.length === 0) return null;
  return (
    <div
      className="absolute left-0 right-0 grid grid-cols-7 pointer-events-none"
      style={{ top: BAR_TOP, zIndex: 3 }}
      aria-hidden="true"
    >
      {segments.map((s) => (
        <span
          key={s.entry.id}
          // Schrift und Innenabstand wie bei der Tages-Kachel.
          className="text-2xs font-semibold flex items-center px-1 overflow-hidden whitespace-nowrap"
          style={{
            gridColumn: `${s.col1} / ${s.col2}`,
            gridRow: s.lane + 1,
            height: BAR_HEIGHT,
            marginBottom: BAR_GAP,
            // An der Wochengrenze laeuft der Balken bis an den Rand, damit er
            // sichtbar weitergeht. Am echten Anfang und Ende rueckt er ein.
            marginLeft: s.openLeft ? 0 : BAR_INSET,
            marginRight: s.openRight ? 0 : BAR_INSET,
            // An der Wochengrenze eckig, damit man sieht dass es weitergeht.
            borderTopLeftRadius: s.openLeft ? 0 : BAR_RADIUS,
            borderBottomLeftRadius: s.openLeft ? 0 : BAR_RADIUS,
            borderTopRightRadius: s.openRight ? 0 : BAR_RADIUS,
            borderBottomRightRadius: s.openRight ? 0 : BAR_RADIUS,
            // Volle Farbe wie bei der Tages-Kachel, sonst sieht derselbe Termin
            // als Balken anders aus als als Kachel.
            backgroundColor: s.entry.color,
            color: s.entry.ink ?? "#fff",
          }}
        >
          {s.openLeft ? "… " : ""}
          {s.entry.title}
          {s.openRight ? " …" : ""}
        </span>
      ))}
    </div>
  );
}
