"use client";

import { useCallback, useEffect, useState } from "react";
import { backendApi } from "@/lib/api";

export interface JobHistoryEntry {
  job_uuid: string;
  original_filename: string;
  created_at: string;
}

interface Eintrag extends JobHistoryEntry {
  tool: string;
  has_download: boolean;
}

/** The last finished jobs of one tool, so one of them can be opened again. */
export function useJobHistory(toolFilter: string, limit = 10) {
  const [eintraege, setEintraege] = useState<JobHistoryEntry[]>([]);

  const laden = useCallback(async () => {
    try {
      const antwort = await backendApi.fetch(`/jobs/my?tool_filter=${toolFilter}&limit=${limit}`);
      if (!antwort.ok) return;
      const { jobs } = (await antwort.json()) as { jobs: Eintrag[] };
      setEintraege(jobs.filter((j) => j.has_download).slice(0, limit));
    } catch {
      // Without the history the tool still works, the list simply stays as it was.
    }
  }, [toolFilter, limit]);

  useEffect(() => {
    void laden();
    const neu = () => { void laden(); };
    window.addEventListener("kis-jobs-changed", neu);
    return () => window.removeEventListener("kis-jobs-changed", neu);
  }, [laden]);

  return eintraege;
}
