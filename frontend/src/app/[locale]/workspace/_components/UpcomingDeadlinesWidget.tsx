"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { ArrowRight, CalendarBlank, CaretDown } from "@phosphor-icons/react";
import { ScheduleTimeline } from "@/components/schedule/ScheduleTimeline";
import { ScheduleEntryCardGlobal, type ScheduleListEntry } from "@/components/schedule/ScheduleEntryCardGlobal";

const WIDGET_LIMIT = 3;
const COLLAPSED_STORAGE_KEY = "kis.upcoming-deadlines.collapsed";

async function toggleChecked(workspaceUuid: string, entryId: number, checked: boolean): Promise<boolean> {
  try {
    const r = await fetch(
      `/api/ai-assistant/workspaces/${workspaceUuid}/schedule/entries/${entryId}`,
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

async function fetchUpcoming(): Promise<ScheduleListEntry[] | null> {
  try {
    const r = await fetch(
      `/api/ai-assistant/schedule/upcoming?limit=${WIDGET_LIMIT}&include_checked=false`,
      { credentials: "include" },
    );
    if (!r.ok) return null;
    const data = await r.json();
    return data.entries || [];
  } catch {
    return null;
  }
}

export default function UpcomingDeadlinesWidget() {
  const t = useTranslations("workspace.list");
  const [entries, setEntries] = useState<ScheduleListEntry[] | null>(null);
  const [error, setError] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    try { return window.localStorage.getItem(COLLAPSED_STORAGE_KEY) === "1"; } catch { return false; }
  });

  useEffect(() => {
    try { window.localStorage.setItem(COLLAPSED_STORAGE_KEY, collapsed ? "1" : "0"); } catch { /* ignore */ }
  }, [collapsed]);

  useEffect(() => {
    let cancelled = false;
    fetchUpcoming().then((items) => {
      if (cancelled) return;
      if (items === null) setError(true);
      else setEntries(items);
    });
    return () => { cancelled = true; };
  }, []);

  const handleToggleChecked = useCallback(async (entry: ScheduleListEntry, checked: boolean) => {
    setEntries((prev) => prev?.map((e) => e.id === entry.id ? { ...e, is_checked: checked } : e) ?? prev);
    const ok = await toggleChecked(entry.workspace_uuid, entry.id, checked);
    if (!ok) {
      setEntries((prev) => prev?.map((e) => e.id === entry.id ? { ...e, is_checked: !checked } : e) ?? prev);
      return;
    }
    await new Promise((res) => setTimeout(res, 600));
    const items = await fetchUpcoming();
    if (items !== null) setEntries(items);
  }, []);

  if (error) return null;
  if (entries === null) return null;
  if (entries.length === 0) return null;

  return (
    <section
      className="mb-6 rounded-lg overflow-hidden"
      style={{ backgroundColor: "var(--background)", border: "1px solid var(--border)" }}
    >
      <header
        role="button"
        tabIndex={0}
        onClick={() => setCollapsed((v) => !v)}
        onKeyDown={(ev) => {
          if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            setCollapsed((v) => !v);
          }
        }}
        aria-expanded={!collapsed}
        className="row-expandable flex items-center justify-between px-4 py-3 cursor-pointer"
        style={{
          borderBottom: collapsed ? "none" : "1px solid var(--border)",
          backgroundColor: "var(--border)",
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="row-caret inline-flex"
            style={{
              transition: "transform 0.15s ease",
              transform: collapsed ? "rotate(-90deg)" : "rotate(0deg)",
            }}
          >
            <CaretDown size={14} weight="bold" />
          </span>
          <CalendarBlank size={16} weight="bold" style={{ color: "var(--kb)" }} />
          <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
            {t("upcomingTitle")}
          </h3>
        </div>
        <Link
          href="/schedule"
          onClick={(ev) => ev.stopPropagation()}
          onPointerDown={(ev) => ev.stopPropagation()}
          className="inline-flex items-center gap-1 text-xs font-medium rounded-md transition-colors hover:bg-[var(--surface-dim)] -my-2 px-3 py-2"
          style={{ color: "var(--kb)" }}
        >
          {t("showAll")}
          <ArrowRight size={12} weight="bold" />
        </Link>
      </header>

      {!collapsed && (
        <div className="p-8 overflow-x-auto">
          <div className="min-w-150">
            <ScheduleTimeline
              entries={entries}
              renderCard={(entry, ctx) => (
                <ScheduleEntryCardGlobal
                  entry={entry}
                  isPast={ctx.isPast}
                  urgency={ctx.urgency}
                  href={`/workspace/${entry.workspace_uuid}?tab=schedule`}
                  onToggleChecked={(checked) => handleToggleChecked(entry, checked)}
                />
              )}
            />
          </div>
        </div>
      )}
    </section>
  );
}
