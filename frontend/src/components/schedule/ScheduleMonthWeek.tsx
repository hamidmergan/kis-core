"use client";

import { useTranslations } from "next-intl";
import type { ScheduleListEntry } from "./ScheduleEntryCardGlobal";
import ScheduleBars, { barsSpace, BAR_TOP, BAR_GAP } from "./ScheduleBars";
import { rangesOn, type MonthGrid } from "./_monthGrid";
import { laneCount, weekSegments, type RangeEntry } from "./_ranges";
import { ymd, ymdOf } from "./utils";

/** More entries per day become '+N more', otherwise one day blows the row height. */
const MAX_CHIPS = 2;

/** At most this many bars on top of each other, the rest counts into '+N more'. */
const MAX_LANES = 2;

/** Today only carries a top edge, the same mark the mini calendar uses. */
const HEUTE_KANTE: React.CSSProperties = {
  top: 0,
  left: 0,
  right: 0,
  height: 3,
  backgroundColor: "var(--kb)",
};

interface Props {
  y: number;
  m: number;
  /** Zero based row of the grid. */
  week: number;
  grid: MonthGrid;
  /** The spans drawn as bars, already without the hidden ones. */
  bars: RangeEntry[];
  /** Whether the grid shows this entry, the lists keep the hidden ones. */
  inGrid: (e: ScheduleListEntry) => boolean;
  today: string;
  selected: string | null;
  colorFor: (uuid: string | null) => string;
  onDayClick: (iso: string) => void;
}

/** One week of the month grid, its own block so the bars can sit inside it. */
export default function ScheduleMonthWeek({ y, m, week: w, grid, bars, inGrid, today, selected, colorFor, onDayClick }: Props) {
  const t = useTranslations("schedule");
  const { startCol, daysInMonth, daysInPrev, byDay, monthRanges } = grid;

  // The day may run past the month, Date converts that.
  const weekStart = ymdOf(new Date(y, m, 1 - startCol + w * 7));
  const segmente = weekSegments(bars, weekStart);
  // Whatever exceeds the cap is not drawn but counted.
  const sichtbareBalken = segmente.filter((s) => s.lane < MAX_LANES);
  const versteckteIds = new Set(
    segmente.filter((s) => s.lane >= MAX_LANES).map((s) => s.entry.id),
  );
  // Space per day instead of per week, otherwise empty cells gape.
  const spurProTag = new Map<number, number>();
  for (const seg of sichtbareBalken) {
    for (let i = seg.col1 - 1; i <= seg.col2 - 2; i++) {
      spurProTag.set(i, Math.max(spurProTag.get(i) ?? -1, seg.lane));
    }
  }
  const wochenPlatz = barsSpace(laneCount(sichtbareBalken));

  return (
    <div
      className="relative grid grid-cols-7 xl:flex-1"
      // Many bars need real height, otherwise the tile below slips out of the cell.
      style={{
        borderTop: w === 0 ? undefined : "1px solid var(--border-soft)",
        ...(wochenPlatz ? { minHeight: BAR_TOP + wochenPlatz + BAR_GAP } : {}),
      }}
    >
      {Array.from({ length: 7 }, (_, i) => {
        const day = w * 7 + i - startCol + 1;
        if (day < 1 || day > daysInMonth) {
          return (
            <div
              key={`out-${w}-${i}`}
              aria-hidden="true"
              className="min-h-13 md:min-h-19 px-1.5 py-1 text-2xs font-semibold"
              style={{
                borderLeft: i === 0 ? undefined : "1px solid var(--border-soft)",
                color: "var(--border)",
              }}
            >
              {day < 1 ? daysInPrev + day : day - daysInMonth}
            </div>
          );
        }
        const iso = ymd(y, m, day);
        const items = (byDay.get(iso) ?? []).filter(inGrid);
        // A span without a bar counts into the same remainder as an omitted tile.
        const versteckteSpannen = rangesOn(monthRanges, iso).filter((r) => versteckteIds.has(r.id)).length;
        const spur = spurProTag.get(i);
        const platz = spur === undefined ? 0 : barsSpace(spur + 1);
        const gesamt = items.length + versteckteSpannen;
        const isToday = iso === today;
        const isSelected = iso === selected;
        const chips = gesamt > MAX_CHIPS + 1 ? items.slice(0, MAX_CHIPS) : items;
        const restChips = gesamt - chips.length;

        return (
          <button
            key={iso}
            type="button"
            onClick={() => onDayClick(iso)}
            aria-pressed={isSelected}
            className="relative min-h-13 md:min-h-19 px-1.5 py-1 flex flex-col text-left transition-colors cursor-pointer hover:bg-[var(--surface-dim)] hover:outline-2 hover:outline-[var(--kb)]"
            style={{
              borderLeft: i === 0 ? undefined : "1px solid var(--border-soft)",
              // The selected day gets the full outline, today only the top edge below.
              outline: isSelected ? "2px solid var(--kb)" : undefined,
              outlineOffset: -2,
              backgroundColor: "var(--background)",
            }}
          >
            {isToday && (
              <span aria-hidden="true" className="absolute pointer-events-none" style={HEUTE_KANTE} />
            )}
            <span
              className="text-2xs font-semibold"
              // Fixed height, otherwise the gap is off by a pixel.
              style={{ height: 17, color: isToday ? "var(--kb)" : "var(--foreground-soft)" }}
            >
              {day}
            </span>

            {/* The space for the bars sits below the number, never above. */}
            {platz > 0 && <span aria-hidden="true" style={{ height: platz }} />}

            {/* The same tiles everywhere, in narrow cells truncate shortens the title. */}
            <span className="flex flex-col gap-0.5 min-w-0">
              {chips.map((e) => (
                <span
                  key={e.id}
                  title={e.title}
                  className="text-2xs font-semibold rounded px-1 py-px truncate"
                  style={{
                    backgroundColor: colorFor(e.workspace_uuid),
                    color: "#fff",
                    opacity: e.is_checked ? 0.45 : 1,
                    textDecoration: e.is_checked ? "line-through" : undefined,
                  }}
                >
                  {e.title}
                </span>
              ))}
              {restChips > 0 && (
                <span
                  className="text-2xs font-bold px-1"
                  style={{ color: "var(--kb)" }}
                >
                  {/* The word "more" fits beside the number only from tablet up. */}
                  <span className="md:hidden">+{restChips}</span>
                  <span className="hidden md:inline">{t("month.more", { count: restChips })}</span>
                </span>
              )}
            </span>
          </button>
        );
      })}
      <ScheduleBars segments={sichtbareBalken} />
    </div>
  );
}
