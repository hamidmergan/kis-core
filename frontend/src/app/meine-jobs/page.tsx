"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";

interface MyJob {
  job_uuid: string;
  tool_label: string;
  original_filename: string;
  status: "pending" | "running" | "success" | "failed";
  error: string | null;
  created_at: string;
  has_download: boolean;
  result_filename: string | null;
}

const isActive = (s: MyJob["status"]) => s === "pending" || s === "running";
const isExpired = (job: MyJob) => job.status === "success" && !job.has_download;

function StatusBadge({ status, expired }: { status: MyJob["status"]; expired: boolean }) {
  if (expired)
    return <span className="inline-flex text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">Abgelaufen</span>;
  if (status === "success")
    return <span className="inline-flex text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">Fertig</span>;
  if (status === "failed")
    return <span className="inline-flex text-xs font-medium text-red-700 bg-red-100 px-2 py-0.5 rounded-full">Fehler</span>;
  if (status === "running")
    return <span className="inline-flex text-xs font-medium text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full animate-pulse">Läuft</span>;
  return <span className="inline-flex text-xs font-medium text-yellow-700 bg-yellow-100 px-2 py-0.5 rounded-full">Wartend</span>;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + "Z").toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function MeineJobsPage() {
  const [jobs, setJobs] = useState<MyJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    fetch("/api/jobs/my?limit=100", { credentials: "include" })
      .then((r) => {
        if (r.status === 401) { router.push("/login"); return null; }
        return r.json();
      })
      .then((data) => {
        if (!data) return;
        // Only show jobs from the last 24 hours
        const cutoff = Date.now() - 24 * 60 * 60 * 1000;
        const recent = (data.jobs ?? []).filter(
          (j: MyJob) => new Date(j.created_at + "Z").getTime() >= cutoff
        );
        setJobs(recent);
      })
      .finally(() => setLoading(false));
  }, [router]);

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
    } finally {
      setCancelling(null);
    }
  };

  return (
    <>
      <Header showLogout />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <h2 className="text-lg font-semibold text-gray-800 mb-1">Meine Jobs (letzte 24 Stunden)</h2>
        <p className="text-sm text-gray-500 mb-6">
          Die letzten 5 fertigen Jobs können heruntergeladen werden. Ältere Dateien werden automatisch entfernt.
        </p>

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : jobs.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-16">Keine Jobs in den letzten 24 Stunden</p>
        ) : (
          <ul className="divide-y divide-gray-100 border border-gray-200 rounded-xl overflow-hidden">
            {jobs.map((job) => {
              const expired = isExpired(job);
              return (
                <li key={job.job_uuid} className={`px-5 py-4 bg-white ${expired ? "opacity-50" : "hover:bg-gray-50"}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-800">{job.tool_label}</p>
                      <p className="text-xs text-gray-400 truncate mt-0.5">{job.original_filename}</p>
                      <p className="text-xs text-gray-400 mt-0.5">{formatDate(job.created_at)}</p>
                      {job.status === "failed" && job.error && (
                        <p className="text-xs text-red-500 mt-1">{job.error}</p>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-2 shrink-0">
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
      </main>
    </>
  );
}
