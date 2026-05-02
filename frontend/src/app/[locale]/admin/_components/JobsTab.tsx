"use client";

import { useEffect, useState } from "react";
import { Stack } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDate, formatDuration } from "@/lib/format";
import { JobStatusBadge, type AdminJob } from "../_shared";

const PAGE_SIZE_OPTIONS = [
  { value: "50", label: "50 pro Seite" },
  { value: "100", label: "100 pro Seite" },
] as const;

export default function JobsTab() {
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [cancelling, setCancelling] = useState<string | null>(null);

  const handleCancel = async (jobUuid: string) => {
    if (!confirm("Job abbrechen und löschen?")) return;
    setCancelling(jobUuid);
    try {
      await fetch(`/api/admin/jobs/${jobUuid}`, { method: "DELETE", credentials: "include" });
      setJobs((prev) => prev.filter((j) => j.job_uuid !== jobUuid));
      setTotal((t) => t - 1);
      window.dispatchEvent(new Event("kis-jobs-changed"));
    } finally {
      setCancelling(null);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 350);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    setOffset(0);
  }, [debouncedQ, limit, dateFrom, dateTo]);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
      q: debouncedQ,
    });
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    fetch(`/api/admin/jobs?${params}`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        setJobs(d.jobs ?? []);
        setTotal(d.total ?? 0);
      })
      .finally(() => setLoading(false));
  }, [limit, offset, debouncedQ, dateFrom, dateTo]);

  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Suche: User, Tool, Datei..."
          className="flex-1 min-w-[200px] text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          title="Von"
          className="text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          title="Bis"
          className="text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
        <Select
          value={String(limit)}
          onChange={(v) => setLimit(Number(v))}
          options={PAGE_SIZE_OPTIONS}
          className="w-40"
        />
        <span className="text-xs text-muted-soft whitespace-nowrap">
          {total} Ergebnis{total !== 1 ? "se" : ""}
        </span>
      </div>

      {loading ? (
        <Spinner className="flex justify-center py-12" />
      ) : jobs.length === 0 ? (
        <EmptyState
          size="lg"
          icon={<Stack size={32} weight="bold" />}
          text="Keine Jobs gefunden"
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border-soft rounded-xl overflow-hidden">
            <thead className="bg-surface text-xs text-muted uppercase">
              <tr>
                <th className="px-4 py-3 text-left">User</th>
                <th className="px-4 py-3 text-left">Tool</th>
                <th className="px-4 py-3 text-left">Datei</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-right">Renderzeit</th>
                <th className="px-4 py-3 text-left">Erstellt</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-soft bg-background">
              {jobs.map((j) => {
                const isActive = j.status === "pending" || j.status === "running";
                return (
                  <tr key={j.job_uuid}>
                    <td className="px-4 py-3 text-foreground-soft whitespace-nowrap">
                      {j.user_display_name}
                    </td>
                    <td className="px-4 py-3 text-foreground-soft whitespace-nowrap">{j.tool_label}</td>
                    <td className="px-4 py-3 text-muted max-w-[200px] truncate">
                      {j.original_filename}
                    </td>
                    <td className="px-4 py-3">
                      <JobStatusBadge status={j.status} />
                    </td>
                    <td className="px-4 py-3 text-right text-muted text-xs whitespace-nowrap">
                      {formatDuration(j.duration_seconds)}
                    </td>
                    <td className="px-4 py-3 text-muted-soft text-xs whitespace-nowrap">
                      {formatDate(j.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      {isActive && (
                        <button
                          onClick={() => handleCancel(j.job_uuid)}
                          disabled={cancelling === j.job_uuid}
                          className="text-xs text-error hover:underline disabled:opacity-40"
                        >
                          {cancelling === j.job_uuid ? "..." : "Abbrechen"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 pt-2">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={currentPage === 1}
            className="px-3 py-1.5 text-sm border-2 border-border rounded-md transition-colors disabled:opacity-40 enabled:hover:border-[var(--kb)] enabled:hover:text-[var(--kb)]"
          >
            ‹
          </button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            const half = 3;
            let start = Math.max(1, currentPage - half);
            const end = Math.min(totalPages, start + 6);
            start = Math.max(1, end - 6);
            const page = start + i;
            if (page > totalPages) return null;
            return (
              <button
                key={page}
                onClick={() => setOffset((page - 1) * limit)}
                className={`px-3 py-1.5 text-sm border-2 rounded-md transition-colors ${
                  page === currentPage
                    ? "bg-kb text-white border-kb"
                    : "border-border hover:border-[var(--kb)] hover:text-[var(--kb)]"
                }`}
              >
                {page}
              </button>
            );
          })}
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={currentPage === totalPages}
            className="px-3 py-1.5 text-sm border-2 border-border rounded-md transition-colors disabled:opacity-40 enabled:hover:border-[var(--kb)] enabled:hover:text-[var(--kb)]"
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}
