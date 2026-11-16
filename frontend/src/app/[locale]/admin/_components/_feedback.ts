import type { StatusTone } from "@/lib/jobStatusDisplay";

export type Category = "bug" | "idea" | "other";

export type FeedbackStatus = "open" | "parked" | "done";

export const STATUSES: readonly FeedbackStatus[] = ["open", "parked", "done"];

// The stripe on the left tells the status at a glance, without opening the select.
export const STRIPE: Record<FeedbackStatus, string> = {
  open: "var(--error)",
  parked: "var(--warn)",
  done: "var(--success)",
};

export type Attachment = {
  id: number;
  filename: string;
};

export type Entry = {
  id: number;
  category: Category;
  message: string;
  contact: string | null;
  username: string | null;
  page_path: string | null;
  status: FeedbackStatus;
  created_at: string;
  attachments: Attachment[];
};

export const TON: Record<Category, StatusTone> = {
  bug: "error",
  idea: "success",
  other: "muted",
};

export function datum(wert: string): string {
  return new Date(wert).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
}
