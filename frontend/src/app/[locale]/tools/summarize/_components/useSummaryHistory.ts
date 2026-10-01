import { useJobHistory, type JobHistoryEntry } from "@/hooks/useJobHistory";

export type { JobHistoryEntry as SummaryHistoryEntry };

/** The last finished summaries of this person, so one of them can be opened again. */
export function useSummaryHistory() {
  return useJobHistory("summary");
}
