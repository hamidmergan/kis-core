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

/** Palette and the colour of each workspace, private appointments under PRIVAT. */
export interface CalendarColors {
  palette: string[];
  colors: Record<string, string>;
}

/** Group key of private appointments, a workspace uuid never looks like this. */
export const PRIVAT = "privat";

export async function fetchColors(): Promise<CalendarColors | null> {
  try {
    const r = await fetch("/api/ai-assistant/schedule/colors", { credentials: "include" });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

/** The server swaps with whichever group held the colour and returns the new state. */
export async function putColor(group: string, color: number): Promise<CalendarColors | null> {
  try {
    const r = await fetch("/api/ai-assistant/schedule/colors", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ group, color }),
    });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

/** Ticks an appointment, a private one has no workspace in the path. */
export async function putChecked(
  workspaceUuid: string | null,
  entryId: number,
  checked: boolean,
): Promise<boolean> {
  const url = workspaceUuid
    ? `/api/ai-assistant/workspaces/${workspaceUuid}/schedule/entries/${entryId}`
    : `/api/ai-assistant/schedule/entries/${entryId}`;
  try {
    const r = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ is_checked: checked }),
    });
    return r.ok;
  } catch {
    return false;
  }
}

/** Deletes a private appointment, false when the server or the connection refuses. */
export async function deleteEntry(entryId: number): Promise<boolean> {
  try {
    const r = await fetch(`/api/ai-assistant/schedule/entries/${entryId}`, {
      method: "DELETE",
      credentials: "include",
    });
    return r.ok;
  } catch {
    return false;
  }
}
