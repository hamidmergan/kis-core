/** Ein Zeitraum im Monatsraster, geschnitten an den Wochengrenzen. */
export interface RangeEntry {
  id: number;
  title: string;
  due_date: string;
  end_date: string;
  color: string;
  /** Setzt die Schriftfarbe im Balken, wenn die aus der Farbe abgeleitete zu blass waere. */
  ink?: string;
}

export interface Segment {
  entry: RangeEntry;
  /** Rasterspalte 1 bis 8, direkt fuer grid-column verwendbar. */
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

/** Alle Zeitraeume, die diese Woche beruehren, mit Spalten und Spur. */
export function weekSegments(ranges: RangeEntry[], weekStartISO: string): Segment[] {
  const weekEndISO = addDays(weekStartISO, 6);
  const treffer = ranges
    .filter((r) => r.due_date <= weekEndISO && r.end_date >= weekStartISO)
    .sort((a, b) => a.due_date.localeCompare(b.due_date) || a.id - b.id);

  // Eine Spur ist frei, sobald ihr letztes Segment vor dem neuen endet.
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

/** Wie viele Spuren die Woche braucht, bestimmt ihre Hoehe. */
export function laneCount(segments: Segment[]): number {
  return segments.reduce((max, s) => Math.max(max, s.lane + 1), 0);
}
