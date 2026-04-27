"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, CalendarBlank, CaretDown } from "@phosphor-icons/react";
import { ScheduleTimeline } from "@/components/schedule/ScheduleTimeline";
import { ScheduleEntryCardGlobal, type ScheduleListEntry } from "@/components/schedule/ScheduleEntryCardGlobal";

const WIDGET_LIMIT = 3;

export default function UpcomingDeadlinesWidget() {
  const [entries, setEntries] = useState<ScheduleListEntry[] | null>(null);
  const [error, setError] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/ki-assistent/schedule/upcoming?limit=${WIDGET_LIMIT}`, {
      credentials: "include",
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => { if (!cancelled) setEntries(data.entries || []); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, []);

  if (error) return null;
  if (entries === null) return null;
  if (entries.length === 0) return null;

  return (
    <section
      className="mb-6 rounded-2xl overflow-hidden"
      style={{ backgroundColor: "var(--bg)", border: "1px solid var(--border)" }}
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
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:opacity-90 transition-opacity"
        style={{
          borderBottom: collapsed ? "none" : "1px solid var(--border)",
          backgroundColor: "var(--border)",
        }}
      >
        <div className="flex items-center gap-2">
          <CaretDown
            size={14}
            weight="bold"
            style={{
              color: "var(--muted)",
              transition: "transform 0.15s ease",
              transform: collapsed ? "rotate(-90deg)" : "rotate(0deg)",
            }}
          />
          <CalendarBlank size={16} weight="bold" style={{ color: "var(--kb)" }} />
          <h3 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            Nächste Termine
          </h3>
        </div>
        <Link
          href="/schedule"
          onClick={(ev) => ev.stopPropagation()}
          className="inline-flex items-center gap-1 text-xs font-medium hover:opacity-70 transition-opacity"
          style={{ color: "var(--kb)" }}
        >
          Alle anzeigen
          <ArrowRight size={12} weight="bold" />
        </Link>
      </header>

      {!collapsed && (
        <div className="px-3 py-2">
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
        </div>
      )}
    </section>
  );
}
