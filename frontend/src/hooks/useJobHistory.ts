"use client";

import { useCallback, useEffect, useState } from "react";
import { backendApi } from "@/lib/api";

export interface JobHistoryEntry {
  job_uuid: string;
  original_filename: string;
  created_at: string;
  status: string;
}

export interface JobHistoryRow extends JobHistoryEntry {
  tool: string;
  has_download: boolean;
}

const fertig = (j: JobHistoryRow) => j.has_download;

/** The last jobs of one tool that can be opened again, by default only the finished ones. */
export function useJobHistory(toolFilter: string, limit = 10, oeffnbar: (j: JobHistoryRow) => boolean = fertig) {
  const [eintraege, setEintraege] = useState<JobHistoryEntry[]>([]);

  const laden = useCallback(async () => {
    try {
      const antwort = await backendApi.fetch(`/jobs/my?tool_filter=${toolFilter}&limit=${limit}`);
      if (!antwort.ok) return;
      const { jobs } = (await antwort.json()) as { jobs: JobHistoryRow[] };
      setEintraege(jobs.filter(oeffnbar).slice(0, limit));
    } catch {
      // Without the history the tool still works, the list simply stays as it was.
    }
  }, [toolFilter, limit, oeffnbar]);

  useEffect(() => {
    void laden();
    const neu = () => { void laden(); };
    window.addEventListener("kis-jobs-changed", neu);
    return () => window.removeEventListener("kis-jobs-changed", neu);
  }, [laden]);

  return eintraege;
}
