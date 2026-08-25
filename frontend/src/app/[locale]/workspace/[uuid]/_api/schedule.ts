import type { ScheduleData, ScheduleEntry, ScheduleEntryType } from "../_types";

const base = (workspaceUuid: string) => `/api/ai-assistant/workspaces/${workspaceUuid}/schedule`;

export async function fetchSchedule(workspaceUuid: string): Promise<ScheduleData> {
  const r = await fetch(base(workspaceUuid), { credentials: "include" });
  if (!r.ok) throw new Error(`Zeitplan laden fehlgeschlagen: ${r.status}`);
  return r.json();
}

export async function generateSchedule(
  workspaceUuid: string,
  sourceIds: string[]
): Promise<{ job_id: number; status: string }> {
  const r = await fetch(`${base(workspaceUuid)}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ source_ids: sourceIds }),
  });
  if (!r.ok) throw new Error(`Generieren fehlgeschlagen: ${r.status}`);
  return r.json();
}

export interface ScheduleJob {
  id: number;
  status: "pending" | "running" | "success" | "failed";
  error: string | null;
  added_count: number;
  source_uuids: string[];
  created_at: string | null;
  updated_at: string | null;
}

export async function fetchScheduleJob(
  workspaceUuid: string,
  jobId: number
): Promise<ScheduleJob> {
  const r = await fetch(`${base(workspaceUuid)}/jobs/${jobId}`, { credentials: "include" });
  if (!r.ok) throw new Error(`Job-Status laden fehlgeschlagen: ${r.status}`);
  return r.json();
}

export interface ActiveScheduleJob {
  active: boolean;
  id?: number;
  status?: "pending" | "running";
  created_at?: string | null;
}

export async function fetchActiveScheduleJob(workspaceUuid: string): Promise<ActiveScheduleJob> {
  const r = await fetch(`${base(workspaceUuid)}/jobs/active`, { credentials: "include" });
  if (!r.ok) throw new Error(`Active-Job-Status laden fehlgeschlagen: ${r.status}`);
  return r.json();
}

export async function createEntry(workspaceUuid: string, input: {
  type: ScheduleEntryType;
  title: string;
  description?: string | null;
  due_date?: string | null;
  end_date?: string | null;
  due_time?: string | null;
  end_time?: string | null;
  date_precision?: "day" | "month";
  is_optional?: boolean;
}): Promise<ScheduleEntry> {
  const r = await fetch(`${base(workspaceUuid)}/entries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  if (!r.ok) throw new Error(`Eintrag anlegen fehlgeschlagen: ${r.status}`);
  return r.json();
}

export async function updateEntry(workspaceUuid: string, entryId: number, patch: Partial<Omit<ScheduleEntry, "id" | "origin" | "source_ids" | "raw_quote" | "created_at" | "updated_at" | "checked_at">> & { clear_date?: boolean; clear_time?: boolean; clear_end_date?: boolean; clear_end_time?: boolean }): Promise<ScheduleEntry> {
  const r = await fetch(`${base(workspaceUuid)}/entries/${entryId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`Aktualisieren fehlgeschlagen: ${r.status}`);
  return r.json();
}

export async function deleteEntry(workspaceUuid: string, entryId: number): Promise<void> {
  const r = await fetch(`${base(workspaceUuid)}/entries/${entryId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!r.ok) throw new Error(`Löschen fehlgeschlagen: ${r.status}`);
}

export async function deleteAllEntries(workspaceUuid: string): Promise<void> {
  const r = await fetch(base(workspaceUuid), {
    method: "DELETE",
    credentials: "include",
  });
  if (!r.ok) throw new Error(`Alles löschen fehlgeschlagen: ${r.status}`);
}
