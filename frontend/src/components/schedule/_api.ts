import type { ScheduleListEntry } from "./ScheduleEntryCardGlobal";

/** The calendar always shows everything, a month with holes would be no calendar. */
export async function fetchAllEntries(): Promise<ScheduleListEntry[] | null> {
  const params = new URLSearchParams({
    include_past_open: "true",
    include_checked: "true",
  });
  try {
    const r = await fetch(`/api/ai-assistant/schedule/upcoming?${params.toString()}`, {
      credentials: "include",
    });
    if (!r.ok) return null;
    const data = await r.json();
    return data.entries || [];
  } catch {
    return null;
  }
}
