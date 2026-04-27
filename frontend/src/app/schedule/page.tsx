"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CalendarBlank } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Spinner from "@/components/ui/Spinner";
import { ScheduleTimeline } from "@/components/schedule/ScheduleTimeline";
import { ScheduleEntryCardGlobal, type ScheduleListEntry } from "@/components/schedule/ScheduleEntryCardGlobal";

const PAGE_SIZE = 20;

async function fetchPage(offset: number, hide: boolean): Promise<{ items: ScheduleListEntry[]; done: boolean } | null> {
  try {
    const r = await fetch(
      `/api/ki-assistent/schedule/upcoming?limit=${PAGE_SIZE}&offset=${offset}&include_checked=${!hide}`,
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

export default function SchedulePage() {
  const [entries, setEntries] = useState<ScheduleListEntry[]>([]);
  const [hideChecked, setHideChecked] = useState(true);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const sentinelRef = useRef<HTMLDivElement | null>(null);
  // Refs mirror state so the IntersectionObserver callback never reads stale closures.
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const offsetRef = useRef(0);
  const hideCheckedRef = useRef(hideChecked);
  hideCheckedRef.current = hideChecked;

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

    fetchPage(0, hideChecked).then((res) => {
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
  }, [hideChecked]);

  const triggerLoadMore = useCallback(async () => {
    if (loadingRef.current || !hasMoreRef.current) return;
    loadingRef.current = true;
    setLoadingMore(true);
    const res = await fetchPage(offsetRef.current, hideCheckedRef.current);
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

  return (
    <ProtectedRoute>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 md:px-8 pt-10 pb-20 lg:pt-15 lg:pb-30">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold flex items-center gap-2" style={{ color: "var(--text)" }}>
            <CalendarBlank size={20} weight="bold" style={{ color: "var(--kb)" }} />
            Mein Zeitplan
          </h1>
          <label className="inline-flex items-center gap-2 cursor-pointer text-xs">
            <input
              type="checkbox"
              checked={hideChecked}
              onChange={(e) => setHideChecked(e.target.checked)}
              className="w-3.5 h-3.5 flex-shrink-0 accent-primary"
            />
            <span style={{ color: "var(--text)" }}>Erledigte ausblenden</span>
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
