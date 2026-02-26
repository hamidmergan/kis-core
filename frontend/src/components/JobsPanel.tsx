"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

interface MyJob {
  job_uuid: string;
  tool: string;
  tool_label: string;
  original_filename: string;
  status: "pending" | "running" | "success" | "failed";
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  expires_at: string | null;
  has_download: boolean;
  result_filename: string | null;
}

const isActive = (s: MyJob["status"]) => s === "pending" || s === "running";
const isExpired = (job: MyJob) => job.status === "success" && !job.has_download;

function timeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr + "Z").getTime()) / 1000);
  if (diff < 60) return "gerade eben";
  if (diff < 3600) return `vor ${Math.floor(diff / 60)} Min.`;
  if (diff < 86400) return `vor ${Math.floor(diff / 3600)} Std.`;
  return `vor ${Math.floor(diff / 86400)} Tagen`;
}

function formatDuration(ms: number): string {
  const totalSec = Math.round(ms / 1000);
  if (totalSec < 60) return `${totalSec}s`;
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function toMs(dateStr: string): number {
  return new Date(dateStr + "Z").getTime();
}

function StatusBadge({ status, expired }: { status: MyJob["status"]; expired: boolean }) {
  if (expired)
    return <span className="text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">Abgelaufen</span>;
  if (status === "success")
    return <span className="text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">Fertig</span>;
  if (status === "failed")
    return <span className="text-xs font-medium text-red-700 bg-red-100 px-2 py-0.5 rounded-full">Fehler</span>;
  if (status === "running")
    return <span className="text-xs font-medium text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full animate-pulse">Läuft</span>;
  return <span className="text-xs font-medium text-yellow-700 bg-yellow-100 px-2 py-0.5 rounded-full">Wartend</span>;
}

export default function JobsPanel() {
  const [open, setOpen] = useState(false);
  const [jobs, setJobs] = useState<MyJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const bgPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch("/api/jobs/my?limit=6", { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      setJobs(data.jobs ?? []);
    } catch {
      // silently ignore
    }
  }, []);

  // Fetch on mount so the badge shows immediately after login
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Refresh immediately when any tool page starts or cancels a job
  useEffect(() => {
    const handler = () => fetchJobs();
    window.addEventListener("kis-jobs-changed", handler);
    return () => window.removeEventListener("kis-jobs-changed", handler);
  }, [fetchJobs]);

  // Background poll every 10s when panel is closed but there are active jobs
  useEffect(() => {
    if (open) {
      if (bgPollRef.current) clearInterval(bgPollRef.current);
      return;
    }
    const hasActive = jobs.some((j) => isActive(j.status));
    if (hasActive) {
      bgPollRef.current = setInterval(fetchJobs, 10000);
    } else {
      if (bgPollRef.current) clearInterval(bgPollRef.current);
    }
    return () => { if (bgPollRef.current) clearInterval(bgPollRef.current); };
  }, [jobs, open, fetchJobs]);

  // Poll every 5s when panel is open
  useEffect(() => {
    if (!open) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    setLoading(true);
    fetchJobs().finally(() => setLoading(false));
    pollRef.current = setInterval(fetchJobs, 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [open, fetchJobs]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const activeCount = jobs.filter((j) => isActive(j.status)).length;

  const handleDownload = (job: MyJob) => {
    const a = document.createElement("a");
    a.href = `/api/jobs/${job.job_uuid}/download`;
    a.download = job.result_filename || "download";
    a.click();
  };

  const handleCancel = async (job: MyJob) => {
    setCancelling(job.job_uuid);
    try {
      await fetch(`/api/jobs/${job.job_uuid}`, { method: "DELETE", credentials: "include" });
      setJobs((prev) => prev.filter((j) => j.job_uuid !== job.job_uuid));
    } catch {
      // silently ignore
    } finally {
      setCancelling(null);
    }
  };

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Meine Jobs"
        className="relative flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <span>Jobs</span>
        {activeCount > 0 && (
          <span className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-blue-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {activeCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-[min(20rem,calc(100vw-1rem))] bg-white border border-gray-200 rounded-xl shadow-lg z-50">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-800">Meine Jobs</span>
            {loading && (
              <div className="w-3.5 h-3.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            )}
          </div>

          <div className="px-4 py-2 bg-blue-50 border-b border-blue-100">
            <p className="text-xs text-blue-700">
              Fertige Jobs können hier heruntergeladen werden — auch nach dem Schließen des Tabs.
              Es werden max. 5 Downloads gespeichert.
            </p>
          </div>

          <div className="max-h-80 overflow-y-auto">
            {jobs.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">Keine Jobs vorhanden</p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {jobs.map((job) => {
                  const expired = isExpired(job);
                  return (
                    <li key={job.job_uuid} className={`px-4 py-3 ${expired ? "opacity-50" : ""}`}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-gray-800 truncate">{job.tool_label}</p>
                          <p className="text-xs text-gray-400 truncate mt-0.5">{job.original_filename}</p>
                          <p className="text-xs text-gray-400 mt-0.5">{timeAgo(job.created_at)}</p>
                          {(job.started_at || job.completed_at) && (
                            <p className="text-xs text-gray-300 mt-0.5">
                              {job.started_at && (
                                <>Warte: {formatDuration(toMs(job.started_at) - toMs(job.created_at))}</>
                              )}
                              {job.started_at && job.completed_at && (
                                <> · Arbeit: {formatDuration(toMs(job.completed_at) - toMs(job.started_at))}</>
                              )}
                            </p>
                          )}
                          {job.status === "failed" && job.error && (
                            <p className="text-xs text-red-500 mt-1 line-clamp-2">{job.error}</p>
                          )}
                        </div>
                        <div className="flex flex-col items-end gap-1.5 shrink-0">
                          <StatusBadge status={job.status} expired={expired} />
                          {job.has_download && (
                            <button
                              onClick={() => handleDownload(job)}
                              className="text-xs text-[#0066cc] hover:underline"
                            >
                              Download
                            </button>
                          )}
                          {isActive(job.status) && (
                            <button
                              onClick={() => handleCancel(job)}
                              disabled={cancelling === job.job_uuid}
                              className="text-xs text-red-500 hover:underline disabled:opacity-50"
                            >
                              {cancelling === job.job_uuid ? "..." : "Abbrechen"}
                            </button>
                          )}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="px-4 py-2.5 border-t border-gray-100 text-center">
            <Link
              href="/meine-jobs"
              onClick={() => setOpen(false)}
              className="text-xs text-[#0066cc] hover:underline"
            >
              Alle Jobs der letzten 24 Stunden
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
