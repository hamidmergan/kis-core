"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CalendarBlank } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Spinner from "@/components/ui/Spinner";
import { ScheduleTimeline } from "@/components/schedule/ScheduleTimeline";
import { ScheduleEntryCardGlobal, type ScheduleListEntry } from "@/components/schedule/ScheduleEntryCardGlobal";

const PAGE_SIZE = 20;

async function fetchPage(offset: number, showAll: boolean): Promise<{ items: ScheduleListEntry[]; done: boolean } | null> {
  const params = new URLSearchParams({
    limit: String(PAGE_SIZE),
    offset: String(offset),
    include_past_open: showAll ? "true" : "false",
    include_checked: showAll ? "true" : "false",
  });
  try {
    const r = await fetch(
      `/api/ki-assistent/schedule/upcoming?${params.toString()}`,
      { credentials: "include" },
    );
    if (!r.ok) return null;
    const data = await r.json();
    const items: ScheduleListEntry[] = data.entries || [];
    return { items, done: items.length < PAGE_SIZE };
  } catch {
    return null;
  }
}

async function toggleChecked(moduleUuid: string, entryId: number, checked: boolean): Promise<boolean> {
  try {
    const r = await fetch(
      `/api/ki-assistent/modules/${moduleUuid}/schedule/entries/${entryId}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ is_checked: checked }),
      },
    );
    return r.ok;
  } catch {
    return false;
  }
}

export default function SchedulePage() {
  const [entries, setEntries] = useState<ScheduleListEntry[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const sentinelRef = useRef<HTMLDivElement | null>(null);
  // Refs mirror state so the IntersectionObserver callback never reads stale closures.
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const offsetRef = useRef(0);
  const showAllRef = useRef(showAll);
  showAllRef.current = showAll;

  // Reset + initial load whenever the toggle flips.
  useEffect(() => {
    let cancelled = false;
    setEntries([]);
    setError(null);
    setInitialLoading(true);
    setHasMore(true);
    offsetRef.current = 0;
    hasMoreRef.current = true;
    loadingRef.current = true;

    fetchPage(0, showAll).then((res) => {
      if (cancelled) return;
      loadingRef.current = false;
      setInitialLoading(false);
      if (!res) {
        setError("Termine konnten nicht geladen werden");
        return;
      }
      setEntries(res.items);
      offsetRef.current = res.items.length;
      hasMoreRef.current = !res.done;
      setHasMore(!res.done);
    });

    return () => { cancelled = true; };
  }, [showAll]);

  const triggerLoadMore = useCallback(async () => {
    if (loadingRef.current || !hasMoreRef.current) return;
    loadingRef.current = true;
    setLoadingMore(true);
    const res = await fetchPage(offsetRef.current, showAllRef.current);
    loadingRef.current = false;
    setLoadingMore(false);
    if (!res) return;
    setEntries((prev) => [...prev, ...res.items]);
    offsetRef.current += res.items.length;
    hasMoreRef.current = !res.done;
    setHasMore(!res.done);
  }, []);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) triggerLoadMore();
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [triggerLoadMore, entries.length]);

  const handleToggleChecked = useCallback(async (entry: ScheduleListEntry, checked: boolean) => {
    setEntries((prev) => prev.map((e) => e.id === entry.id ? { ...e, is_checked: checked } : e));
    const ok = await toggleChecked(entry.module_uuid, entry.id, checked);
    if (!ok) {
      setEntries((prev) => prev.map((e) => e.id === entry.id ? { ...e, is_checked: !checked } : e));
      return;
    }
    if (!showAllRef.current && checked) {
      await new Promise((res) => setTimeout(res, 600));
      setEntries((prev) => prev.filter((e) => e.id !== entry.id));
    }
  }, []);

  return (
    <ProtectedRoute>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 md:px-8 pt-10 pb-20 lg:pt-15 lg:pb-30">
        <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
          <h1 className="text-xl font-bold flex items-center gap-2" style={{ color: "var(--text)" }}>
            <CalendarBlank size={20} weight="bold" style={{ color: "var(--kb)" }} />
            Mein Zeitplan
          </h1>
          <label className="inline-flex items-center gap-2 text-xs cursor-pointer select-none">
            <span style={{ color: "var(--text)" }}>Alle anzeigen</span>
            <button
              type="button"
              role="switch"
              aria-checked={showAll}
              onClick={() => setShowAll((v) => !v)}
              className="relative inline-block w-9 h-5 rounded-full transition-colors flex-shrink-0"
              style={{ backgroundColor: showAll ? "var(--kb)" : "var(--border)" }}
            >
              <span
                aria-hidden="true"
                className="absolute top-0.5 w-4 h-4 rounded-full transition-transform"
                style={{
                  left: 2,
                  backgroundColor: "#fff",
                  transform: showAll ? "translateX(16px)" : "translateX(0)",
                  boxShadow: "0 1px 2px rgba(0,0,0,.2)",
                }}
              />
            </button>
          </label>
        </div>

        {initialLoading && (
          <div className="flex justify-center py-16">
            <Spinner size="md" />
          </div>
        )}

        {!initialLoading && error && entries.length === 0 && (
          <p className="text-center text-sm py-12" style={{ color: "#B91C1C" }}>{error}</p>
        )}

        {!initialLoading && !error && entries.length === 0 && (
          <div className="flex flex-col items-center gap-3 py-20 text-center">
            <CalendarBlank size={40} weight="light" style={{ color: "var(--muted)" }} />
            <p className="text-sm" style={{ color: "var(--muted)" }}>Keine Termine vorhanden</p>
          </div>
        )}

        {entries.length > 0 && (
          <>
            <ScheduleTimeline
              entries={entries}
              renderCard={(entry, ctx) => (
                <ScheduleEntryCardGlobal
                  entry={entry}
                  isToday={ctx.isToday}
                  isPast={ctx.isPast}
                  urgency={ctx.urgency}
                  href={`/workspaces/${entry.module_uuid}?tab=schedule`}
                  onToggleChecked={(checked) => handleToggleChecked(entry, checked)}
                />
              )}
            />

            <div ref={sentinelRef} aria-hidden="true" />

            {loadingMore && (
              <div className="flex justify-center py-4">
                <Spinner size="sm" />
              </div>
            )}

            {!hasMore && entries.length >= PAGE_SIZE && (
              <p className="text-center text-xs py-4" style={{ color: "var(--muted)" }}>
                Alle Termine geladen
              </p>
            )}
          </>
        )}
      </div>
    </ProtectedRoute>
  );
}
