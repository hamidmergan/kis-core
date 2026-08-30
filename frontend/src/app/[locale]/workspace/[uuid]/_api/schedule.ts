import { genericErrorMessage, parseDetail } from "@/lib/api";
import type { ScheduleData, ScheduleEntry, ScheduleEntryType } from "../_types";

const base = (workspaceUuid: string) => `/api/ai-assistant/workspaces/${workspaceUuid}/schedule`;

/** Never lets a raw status code reach the user - shows the backend's reason, or a friendly fallback. */
async function throwIfNotOk(r: Response): Promise<void> {
  if (r.ok) return;
  const body = await r.json().catch(() => null);
  throw new Error(parseDetail(body?.detail, genericErrorMessage()));
}

export async function fetchSchedule(workspaceUuid: string): Promise<ScheduleData> {
  const r = await fetch(base(workspaceUuid), { credentials: "include" });
  await throwIfNotOk(r);
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
  await throwIfNotOk(r);
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
  await throwIfNotOk(r);
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
  await throwIfNotOk(r);
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
  await throwIfNotOk(r);
  return r.json();
}

export async function updateEntry(workspaceUuid: string, entryId: number, patch: Partial<Omit<ScheduleEntry, "id" | "origin" | "source_ids" | "raw_quote" | "created_at" | "updated_at" | "checked_at">> & { clear_date?: boolean; clear_time?: boolean; clear_end_date?: boolean; clear_end_time?: boolean }): Promise<ScheduleEntry> {
  const r = await fetch(`${base(workspaceUuid)}/entries/${entryId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(patch),
  });
  await throwIfNotOk(r);
  return r.json();
}

export async function deleteEntry(workspaceUuid: string, entryId: number): Promise<void> {
  const r = await fetch(`${base(workspaceUuid)}/entries/${entryId}`, {
    method: "DELETE",
    credentials: "include",
  });
  await throwIfNotOk(r);
}

export async function deleteAllEntries(workspaceUuid: string): Promise<void> {
  const r = await fetch(base(workspaceUuid), {
    method: "DELETE",
    credentials: "include",
  });
  await throwIfNotOk(r);
}
