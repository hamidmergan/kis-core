"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { checkAuthStatus } from "@/lib/auth";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import BackLink from "@/components/ui/BackLink";
import { ArrowsCounterClockwise } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";

import type { MyJob } from "./_types";
import { FilterBar } from "./_components/FilterBar";
import { Pagination } from "./_components/Pagination";
import { JobListItem } from "./_components/JobListItem";
import { DeleteConfirmModal } from "./_components/DeleteConfirmModal";


export default function MeineJobsPage() {
  const t = useTranslations("myJobs");
  const locale = useLocale();
  const [jobs, setJobs] = useState<MyJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const ss = (key: string, fallback: string) => typeof window !== "undefined" ? (sessionStorage.getItem(key) ?? fallback) : fallback;
  const [q, setQ] = useState(() => ss("mj_q", ""));
  const [debouncedQ, setDebouncedQ] = useState(() => ss("mj_q", ""));
  const [toolFilter, setToolFilter] = useState(() => ss("mj_tool", ""));
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(() => Number(ss("mj_limit", "10")));
  const [dateFrom, setDateFrom] = useState(() => ss("mj_from", ""));
  const [dateTo, setDateTo] = useState(() => ss("mj_to", ""));
  const [isAdmin, setIsAdmin] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<MyJob | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const router = useRouter();

  useEffect(() => {
    checkAuthStatus().then((s) => setIsAdmin(s.is_admin ?? false));
  }, []);

  // Debounce q and reset offset
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQ(q);
      setOffset(0);
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [q]);

  // Persist filters to sessionStorage
  useEffect(() => { sessionStorage.setItem("mj_q", q); }, [q]);
  useEffect(() => { sessionStorage.setItem("mj_tool", toolFilter); }, [toolFilter]);
  useEffect(() => { sessionStorage.setItem("mj_limit", String(limit)); }, [limit]);
  useEffect(() => { sessionStorage.setItem("mj_from", dateFrom); }, [dateFrom]);
  useEffect(() => { sessionStorage.setItem("mj_to", dateTo); }, [dateTo]);

  // Reset offset when limit, dates or tool filter change
  useEffect(() => { setOffset(0); }, [limit, dateFrom, dateTo, toolFilter]);

  const resetFilters = () => {
    setQ(""); setToolFilter(""); setDateFrom(""); setDateTo(""); setLimit(10); setOffset(0);
  };
  const hasActiveFilters = !!(q || toolFilter || dateFrom || dateTo);

  const fetchJobs = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
        q: debouncedQ,
      });
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      if (toolFilter) params.set("tool_filter", toolFilter);
      const r = await fetch(`/api/jobs/my?${params}`, { credentials: "include" });
      if (r.status === 401) { router.push("/login"); return; }
      const data = await r.json();
      setJobs(data.jobs ?? []);
      setTotal(data.total ?? 0);
      setLastUpdated(new Date());
    } finally {
      setLoading(false);
    }
  }, [offset, debouncedQ, toolFilter, limit, dateFrom, dateTo, router]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Refresh when JobsPanel detects a status change (e.g. running→success)
  useEffect(() => {
    const handler = () => fetchJobs(true);
    window.addEventListener("kis-jobs-status-changed", handler);
    return () => window.removeEventListener("kis-jobs-status-changed", handler);
  }, [fetchJobs]);

  const handleRetry = async (job: MyJob) => {
    // Translate-stage failures need the wizard: render_params.json is saved at render
    // pipeline start, so the retry endpoint has no params yet, user must redo translate.
    // Render-stage failures re-queue directly with saved params. Routing into the wizard
    // would let the user navigate back and edit scripts/settings, which would silently
    // poison the index-based render_cache (no content-hash check on slide reuse).
    if (job.tool === "screencast_translate") {
      router.push(`/${locale}/tools/screencast?resume=${job.job_uuid}`);
      return;
    }
    setRetrying(job.job_uuid);
    try {
      const res = await fetch(`/api/jobs/${job.job_uuid}/retry`, { method: "POST", credentials: "include" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || t("retryFailed"));
        return;
      }
      await fetchJobs();
    } finally {
      setRetrying(null);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm) return;
    setDeleting(deleteConfirm.job_uuid);
    try {
      await fetch(`/api/jobs/${deleteConfirm.job_uuid}`, { method: "DELETE", credentials: "include" });
      setJobs((prev) => prev.filter((j) => j.job_uuid !== deleteConfirm.job_uuid));
      setTotal((prev) => Math.max(0, prev - 1));
      setDeleteConfirm(null);
    } finally {
      setDeleting(null);
    }
  };

  const handleCancel = async (job: MyJob) => {
    setCancelling(job.job_uuid);
    try {
      await fetch(`/api/jobs/${job.job_uuid}`, { method: "DELETE", credentials: "include" });
      setJobs((prev) => prev.filter((j) => j.job_uuid !== job.job_uuid));
      setTotal((prev) => Math.max(0, prev - 1));
      window.dispatchEvent(new Event("kis-jobs-changed"));
    } finally {
      setCancelling(null);
    }
  };

  return (
    <ProtectedRoute>
      <main className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-xl font-semibold mb-4">{t("title")}</h2>
          <div className="flex items-center gap-2">
            {lastUpdated && !loading && (
              <span className="text-xs text-muted-soft">
                {lastUpdated.toLocaleTimeString(locale === "en" ? "en-US" : "de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" })}
              </span>
            )}
            <button
              onClick={() => { fetchJobs(); window.dispatchEvent(new CustomEvent("kis-jobs-changed")); }}
              disabled={loading}
              title={t("refresh")}
              className="flex items-center gap-1.5 text-sm text-muted hover:text-foreground disabled:opacity-40 transition-colors"
            >
              <ArrowsCounterClockwise size={16} className={loading ? "animate-spin" : ""} />
              {t("refresh")}
            </button>
          </div>
        </div>
        <p className="text-sm text-muted mb-4">
          {t("intro")}
        </p>

        <FilterBar
          q={q}
          toolFilter={toolFilter}
          dateFrom={dateFrom}
          dateTo={dateTo}
          limit={limit}
          total={total}
          hasActiveFilters={hasActiveFilters}
          onQChange={setQ}
          onToolFilterChange={setToolFilter}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
          onLimitChange={setLimit}
          onReset={resetFilters}
        />

        {loading ? (
          <Spinner className="flex justify-center py-16" />
        ) : jobs.length === 0 ? (
          <p className="text-sm text-muted-soft text-center py-16">
            {debouncedQ ? t("emptySearch") : t("emptyAll")}
          </p>
        ) : (
          <>
            <ul className="border border-border-soft divide-y divide-border-soft rounded-xl overflow-hidden">
              {jobs.map((job) => (
                <JobListItem
                  key={job.job_uuid}
                  job={job}
                  isAdmin={isAdmin}
                  cancelling={cancelling}
                  retrying={retrying}
                  onCancel={handleCancel}
                  onRetry={handleRetry}
                  onRequestDelete={setDeleteConfirm}
                />
              ))}
            </ul>

            <Pagination
              total={total}
              offset={offset}
              limit={limit}
              onOffsetChange={setOffset}
            />
          </>
        )}
      </main>

      {deleteConfirm && (
        <DeleteConfirmModal
          job={deleteConfirm}
          deleting={!!deleting}
          onCancel={() => setDeleteConfirm(null)}
          onConfirm={handleDeleteConfirm}
        />
      )}
    </ProtectedRoute>
  );
}
