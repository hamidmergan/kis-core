"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Stack } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDate } from "@/lib/format";
import { notifyJobsChanged } from "@/lib/jobs-events";
import { JobStatusBadge, type AdminJob } from "../_shared";
import Pager from "./Pager";
import { useListFilter } from "./useListFilter";

export default function JobsTab() {
  const t = useTranslations("admin");
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const { q, setQ, limit, setLimit, offset, setOffset, dateFrom, setDateFrom, dateTo, setDateTo, query } = useListFilter();
  const [cancelling, setCancelling] = useState<string | null>(null);

  const pageSizeOptions = useMemo(
    () => [
      { value: "50", label: t("jobs.pageSize", { n: 50 }) },
      { value: "100", label: t("jobs.pageSize", { n: 100 }) },
    ],
    [t],
  );

  const handleCancel = async (jobUuid: string) => {
    if (!confirm(t("jobs.cancelConfirm"))) return;
    setCancelling(jobUuid);
    try {
      const res = await fetch(`/api/admin/jobs/${jobUuid}`, { method: "DELETE", credentials: "include" });
      // A refused cancel keeps the row, the job is still running.
      if (!res.ok) return;
      setJobs((prev) => prev.filter((j) => j.job_uuid !== jobUuid));
      setTotal((n) => n - 1);
      notifyJobsChanged();
    } catch {
      // The row stays for another try.
    } finally {
      setCancelling(null);
    }
  };

  useEffect(() => {
    // A slower answer to an older filter must not replace the newer list.
    let current = true;
    setLoading(true);
    fetch(`/api/admin/jobs?${query}`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        if (!current) return;
        setJobs(d.jobs ?? []);
        setTotal(d.total ?? 0);
      })
      .catch(() => {})
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [query]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("jobs.searchPlaceholder")}
          className="flex-1 min-w-50 text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          title={t("jobs.from")}
          className="text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          title={t("jobs.to")}
          className="text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
        <Select
          value={String(limit)}
          onChange={(v) => setLimit(Number(v))}
          options={pageSizeOptions}
          className="w-40"
        />
        <span className="text-xs text-muted-soft whitespace-nowrap">
          {t("jobs.results", { count: total })}
        </span>
      </div>

      {loading ? (
        <Spinner className="flex justify-center py-12" />
      ) : jobs.length === 0 ? (
        <EmptyState
          size="lg"
          icon={<Stack size={32} weight="bold" />}
          text={t("jobs.empty")}
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border-soft rounded-xl overflow-hidden">
            <thead className="bg-surface text-xs text-muted uppercase">
              <tr>
                <th className="px-4 py-3 text-left">{t("jobs.colUser")}</th>
                <th className="px-4 py-3 text-left">{t("jobs.colTool")}</th>
                <th className="px-4 py-3 text-left">{t("jobs.colFile")}</th>
                <th className="px-4 py-3 text-left">{t("jobs.colStatus")}</th>
                <th className="px-4 py-3 text-left">{t("jobs.colCreated")}</th>
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
                    <td className="px-4 py-3 text-muted max-w-50 truncate">
                      {j.original_filename}
                    </td>
                    <td className="px-4 py-3">
                      <JobStatusBadge status={j.status} />
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
                          {cancelling === j.job_uuid ? "..." : t("jobs.cancel")}
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

      <Pager total={total} limit={limit} offset={offset} onOffset={setOffset} />
    </div>
  );
}
