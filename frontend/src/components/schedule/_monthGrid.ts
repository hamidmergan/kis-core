import type { ScheduleListEntry } from "./ScheduleEntryCardGlobal";
import { PRIVAT } from "./_api";
import { ymd } from "./utils";

/** Everything the month view reads off the entries, sorted into the places it shows them. */
export interface MonthGrid {
  daysInMonth: number;
  daysInPrev: number;
  /** Column of the first of the month, Monday is 0. */
  startCol: number;
  weeks: number;
  /** Single-day entries by their day. */
  byDay: Map<string, ScheduleListEntry[]>;
  /** Entries the source dated only to the month. */
  noDay: ScheduleListEntry[];
  /** Spans touching the month. */
  monthRanges: ScheduleListEntry[];
  /** Workspaces with an entry this month in first-seen order, private ones last under PRIVAT without a title. */
  groups: { key: string; title: string | null }[];
}

/** Spans are drawn by the bar, they must not also appear as a day tile. */
const isRange = (e: ScheduleListEntry) => !!e.end_date && e.end_date !== e.due_date;

export function monthGrid(
  entries: ScheduleListEntry[],
  y: number,
  m: number,
  hiddenGroups: ReadonlySet<string>,
): MonthGrid {
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const daysInPrev = new Date(y, m, 0).getDate();
  const startCol = (new Date(y, m, 1).getDay() + 6) % 7;
  const trailing = (7 - ((startCol + daysInMonth) % 7)) % 7;
  const weeks = (startCol + daysInMonth + trailing) / 7;

  const monthStart = ymd(y, m, 1);
  const monthEnd = ymd(y, m, daysInMonth);
  const monthPrefix = monthStart.slice(0, 7);
  const imMonat = (e: ScheduleListEntry) =>
    isRange(e)
      ? e.due_date <= monthEnd && (e.end_date as string) >= monthStart
      : !!e.due_date && e.due_date.startsWith(monthPrefix);

  // The legend lists hidden workspaces too, otherwise they could not be shown again.
  const groups: MonthGrid["groups"] = [];
  const seen = new Set<string>();
  let hatPrivate = false;
  for (const e of entries.filter(imMonat)) {
    // Private appointments carry no workspace name, they stand as one line.
    if (e.workspace_uuid === null) {
      hatPrivate = true;
      continue;
    }
    if (!seen.has(e.workspace_uuid)) {
      seen.add(e.workspace_uuid);
      groups.push({ key: e.workspace_uuid, title: e.module_title ?? "" });
    }
  }
  if (hatPrivate) groups.push({ key: PRIVAT, title: null });

  // A hidden workspace disappears from the grid and from every list.
  const shown = entries.filter((e) => !hiddenGroups.has(e.workspace_uuid ?? PRIVAT));
  const monthRanges = shown.filter((e) => isRange(e) && imMonat(e));

  // An entry without a day number fits no cell and sits below the grid.
  const byDay = new Map<string, ScheduleListEntry[]>();
  const noDay: ScheduleListEntry[] = [];
  for (const e of shown) {
    if (!e.due_date || !e.due_date.startsWith(monthPrefix)) continue;
    if (isRange(e)) continue;
    if (e.date_precision === "month") {
      noDay.push(e);
      continue;
    }
    const list = byDay.get(e.due_date);
    if (list) list.push(e);
    else byDay.set(e.due_date, [e]);
  }

  return { daysInMonth, daysInPrev, startCol, weeks, byDay, noDay, monthRanges, groups };
}

/** The spans covering one day, a span sits in no cell but makes its days clickable. */
export function rangesOn(monthRanges: ScheduleListEntry[], iso: string): ScheduleListEntry[] {
  return monthRanges.filter((r) => r.due_date <= iso && (r.end_date as string) >= iso);
}
