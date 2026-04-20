import type { ZeitplanData, ZeitplanEntry, ZeitplanEntryType } from "../_types";

const base = (moduleUuid: string) => `/api/ki-assistent/modules/${moduleUuid}/zeitplan`;

export async function fetchZeitplan(moduleUuid: string): Promise<ZeitplanData> {
  const r = await fetch(base(moduleUuid), { credentials: "include" });
  if (!r.ok) throw new Error(`Zeitplan laden fehlgeschlagen: ${r.status}`);
  return r.json();
}

export async function generateZeitplan(
  moduleUuid: string,
  sourceIds: string[]
): Promise<{ job_id: number; status: string }> {
  const r = await fetch(`${base(moduleUuid)}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ source_ids: sourceIds }),
  });
  if (!r.ok) throw new Error(`Generieren fehlgeschlagen: ${r.status}`);
  return r.json();
}

export interface ZeitplanJob {
  id: number;
  status: "pending" | "running" | "success" | "failed";
  error: string | null;
  added_count: number;
  source_uuids: string[];
  created_at: string | null;
  updated_at: string | null;
}

export async function fetchZeitplanJob(
  moduleUuid: string,
  jobId: number
): Promise<ZeitplanJob> {
  const r = await fetch(`${base(moduleUuid)}/jobs/${jobId}`, { credentials: "include" });
  if (!r.ok) throw new Error(`Job-Status laden fehlgeschlagen: ${r.status}`);
  return r.json();
}

export interface ActiveZeitplanJob {
  active: boolean;
  id?: number;
  status?: "pending" | "running";
  created_at?: string | null;
}

export async function fetchActiveZeitplanJob(moduleUuid: string): Promise<ActiveZeitplanJob> {
  const r = await fetch(`${base(moduleUuid)}/jobs/active`, { credentials: "include" });
  if (!r.ok) throw new Error(`Active-Job-Status laden fehlgeschlagen: ${r.status}`);
  return r.json();
}

export async function createEntry(moduleUuid: string, input: {
  type: ZeitplanEntryType;
  title: string;
  description?: string | null;
  due_date?: string | null;
  due_time?: string | null;
  is_optional?: boolean;
}): Promise<ZeitplanEntry> {
  const r = await fetch(`${base(moduleUuid)}/entries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  if (!r.ok) throw new Error(`Eintrag anlegen fehlgeschlagen: ${r.status}`);
  return r.json();
}

export async function updateEntry(moduleUuid: string, entryId: number, patch: Partial<Omit<ZeitplanEntry, "id" | "origin" | "source_ids" | "raw_quote" | "created_at" | "updated_at" | "checked_at">> & { clear_date?: boolean; clear_time?: boolean }): Promise<ZeitplanEntry> {
  const r = await fetch(`${base(moduleUuid)}/entries/${entryId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`Aktualisieren fehlgeschlagen: ${r.status}`);
  return r.json();
}

export async function deleteEntry(moduleUuid: string, entryId: number): Promise<void> {
  const r = await fetch(`${base(moduleUuid)}/entries/${entryId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!r.ok) throw new Error(`Löschen fehlgeschlagen: ${r.status}`);
}

export async function deleteAllEntries(moduleUuid: string): Promise<void> {
  const r = await fetch(base(moduleUuid), {
    method: "DELETE",
    credentials: "include",
  });
  if (!r.ok) throw new Error(`Alles löschen fehlgeschlagen: ${r.status}`);
}
