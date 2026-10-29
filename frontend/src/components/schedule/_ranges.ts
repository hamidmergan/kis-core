/** A span in the month grid, cut at the week boundaries. */
export interface RangeEntry {
  id: number;
  title: string;
  due_date: string;
  end_date: string;
  color: string;
  /** Done means the bar is struck through and pale, like the day tile. */
  is_checked: boolean;
  /** Sets the text colour in the bar when the derived one would be too pale. */
  ink?: string;
}

export interface Segment {
  entry: RangeEntry;
  /** Grid column 1 to 8, usable directly for grid-column. */
  col1: number;
  col2: number;
  openLeft: boolean;
  openRight: boolean;
  lane: number;
}

function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d + n);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

function dayIndex(iso: string, weekStartISO: string): number {
  const [ay, am, ad] = weekStartISO.split("-").map(Number);
  const [by, bm, bd] = iso.split("-").map(Number);
  const a = new Date(ay, am - 1, ad).getTime();
  const b = new Date(by, bm - 1, bd).getTime();
  return Math.round((b - a) / 86_400_000);
}

/** All spans touching this week, with columns and lane. */
export function weekSegments(ranges: RangeEntry[], weekStartISO: string): Segment[] {
  const weekEndISO = addDays(weekStartISO, 6);
  const treffer = ranges
    .filter((r) => r.due_date <= weekEndISO && r.end_date >= weekStartISO)
    .sort((a, b) => a.due_date.localeCompare(b.due_date) || a.id - b.id);

  // A lane is free as soon as its last segment ends before the new one.
  const spurEnde: number[] = [];
  const segmente: Segment[] = [];
  for (const r of treffer) {
    const von = Math.max(dayIndex(r.due_date, weekStartISO), 0);
    const bis = Math.min(dayIndex(r.end_date, weekStartISO), 6);
    let lane = spurEnde.findIndex((ende) => ende < von);
    if (lane === -1) {
      lane = spurEnde.length;
      spurEnde.push(bis);
    } else {
      spurEnde[lane] = bis;
    }
    segmente.push({
      entry: r,
      col1: von + 1,
      col2: bis + 2,
      openLeft: r.due_date < weekStartISO,
      openRight: r.end_date > weekEndISO,
      lane,
    });
  }
  return segmente;
}

/** How many lanes the week needs decides its height. */
export function laneCount(segments: Segment[]): number {
  return segments.reduce((max, s) => Math.max(max, s.lane + 1), 0);
}
