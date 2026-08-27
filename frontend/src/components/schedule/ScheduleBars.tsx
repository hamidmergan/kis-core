"use client";

import type { Segment } from "./_ranges";

/** Height of a bar. */
export const BAR_HEIGHT = 18;
/** One gap for everything, matching the grid gap of the bar layer. */
export const BAR_GAP = 4;
/** Padding 4 plus day number 17, the cell has no border any more. */
const NUMBER_BLOCK = 21;
/** Inset at the real start and end, like the cell's horizontal padding. */
const BAR_INSET = 6;
/** Rounding as on the day tiles (rounded = 4px). */
const BAR_RADIUS = 4;
/** The first bar starts exactly one gap below the day number. */
export const BAR_TOP = NUMBER_BLOCK + BAR_GAP;

/** Placeholder under the number, a bar takes its height plus one gap. */
export function barsSpace(lanes: number): number {
  return lanes === 0 ? 0 : BAR_GAP + lanes * (BAR_HEIGHT + BAR_GAP);
}

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
          // Font and padding as on the day tile.
          className="text-2xs font-semibold flex items-center px-1 overflow-hidden whitespace-nowrap"
          style={{
            gridColumn: `${s.col1} / ${s.col2}`,
            gridRow: s.lane + 1,
            height: BAR_HEIGHT,
            marginBottom: BAR_GAP,
            // At the week boundary the bar runs to the edge, at the real end it insets.
            marginLeft: s.openLeft ? 0 : BAR_INSET,
            marginRight: s.openRight ? 0 : BAR_INSET,
            // Square at the week boundary so you can see it continues.
            borderTopLeftRadius: s.openLeft ? 0 : BAR_RADIUS,
            borderBottomLeftRadius: s.openLeft ? 0 : BAR_RADIUS,
            borderTopRightRadius: s.openRight ? 0 : BAR_RADIUS,
            borderBottomRightRadius: s.openRight ? 0 : BAR_RADIUS,
            // Only a hint of colour with a thin edge, otherwise one week overwhelms the month.
            backgroundColor: `color-mix(in srgb, ${s.entry.color} 18%, transparent)`,
            boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${s.entry.color} 40%, transparent)`,
            color: s.entry.ink ?? "var(--foreground)",
            // Done looks the same on the bar as on the day tile.
            opacity: s.entry.is_checked ? 0.45 : 1,
            textDecoration: s.entry.is_checked ? "line-through" : undefined,
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
