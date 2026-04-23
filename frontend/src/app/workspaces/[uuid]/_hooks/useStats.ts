"use client";

import { useCallback, useEffect, useState } from "react";
import type { StreakInfo, StudentStats } from "../_types";

interface UseStatsOptions {
  uuid: string;
  initialized: boolean;
}

export function useStats({ uuid, initialized }: UseStatsOptions) {
  const [streakInfo, setStreakInfo] = useState<StreakInfo>({ current_streak: 0, max_streak: 0, last_active_date: null });
  const [pageStats, setPageStats] = useState<StudentStats | null>(null);
  const [statsVersion, setStatsVersion] = useState(0);

  const loadStreak = useCallback(async () => {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/streak`, { credentials: "include" });
      if (res.ok) setStreakInfo(await res.json());
    } catch { /* ignore */ }
  }, [uuid]);

  const refreshPageStats = useCallback(() => {
    fetch(`/api/ki-assistent/modules/${uuid}/stats`, { credentials: "include" })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setPageStats(data); })
      .catch(() => { /* ignore */ });
  }, [uuid]);

  const bumpStats = useCallback(() => setStatsVersion((v) => v + 1), []);

  useEffect(() => {
    if (initialized) refreshPageStats();
  }, [initialized, refreshPageStats, statsVersion]);

  useEffect(() => {
    loadStreak();
  }, [loadStreak]);

  return {
    streakInfo,
    pageStats,
    statsVersion,
    loadStreak,
    bumpStats,
  };
}
