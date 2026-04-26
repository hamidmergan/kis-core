"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CalendarBlank } from "@phosphor-icons/react";
import { ScheduleListItem, type ScheduleListEntry } from "@/components/schedule/ScheduleListItem";

const WIDGET_LIMIT = 5;

export default function UpcomingDeadlinesWidget() {
  const router = useRouter();
  const [entries, setEntries] = useState<ScheduleListEntry[] | null>(null);
  const [error, setError] = useState(false);

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
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2">
          <CalendarBlank size={16} weight="bold" style={{ color: "var(--kb)" }} />
          <h3 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            Nächste Termine
          </h3>
        </div>
        <button
          type="button"
          onClick={() => router.push("/schedule")}
          className="inline-flex items-center gap-1 text-xs font-medium hover:opacity-70 transition-opacity"
          style={{ color: "var(--kb)" }}
        >
          Alle anzeigen
          <ArrowRight size={12} weight="bold" />
        </button>
      </header>

      <div className="overflow-x-auto">
        <ul className="min-w-max">
          {entries.map((e, idx) => (
            <ScheduleListItem
              key={e.id}
              entry={e}
              isFirst={idx === 0}
              onClick={() => router.push(`/workspaces/${e.module_uuid}`)}
            />
          ))}
        </ul>
      </div>
    </section>
  );
}
