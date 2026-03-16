"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getToolConfigByJobTool } from "@/lib/toolConfig";

interface MyJob {
  job_uuid: string;
  tool: string;
  tool_label: string;
  original_filename: string;
  status: "pending" | "running" | "success" | "failed" | "awaiting_user" | "queued";
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  expires_at: string | null;
  has_download: boolean;
  result_filename: string | null;
  tts_params?: { voice_id?: string; voice_label?: string; provider?: string } | null;
  is_generating_scripts?: boolean;
}

const SCREENCAST_RENDER_TOOLS = new Set(["screencast_render", "screencast_auto", "screencast_demo_render"]);

const isActive = (s: MyJob["status"]) => s === "pending" || s === "running" || s === "awaiting_user" || s === "queued";
const needsAttention = (s: MyJob["status"]) => isActive(s);
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

function StatusBadge({ status, expired, isGeneratingScripts }: { status: MyJob["status"]; expired: boolean; isGeneratingScripts?: boolean }) {
  if (expired)
    return <span className="text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">Abgelaufen</span>;
  if (status === "success")
    return <span className="text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">Fertig</span>;
  if (status === "failed")
    return <span className="text-xs font-medium text-red-700 bg-red-100 px-2 py-0.5 rounded-full">Fehler</span>;
  if (status === "running" || isGeneratingScripts)
    return <span className="text-xs font-medium text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full animate-pulse">Läuft</span>;
  if (status === "awaiting_user")
    return <span className="text-xs font-medium text-orange-700 bg-orange-100 px-2 py-0.5 rounded-full">Eingabe erforderlich</span>;
  if (status === "queued")
    return <span className="text-xs font-medium text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full">In der Schlange</span>;
  return <span className="text-xs font-medium text-yellow-700 bg-yellow-100 px-2 py-0.5 rounded-full">Wartend</span>;
}

export default function JobsPanel() {
  const [open, setOpen] = useState(false);
  const [jobs, setJobs] = useState<MyJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [bundleDownloading, setBundleDownloading] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const router = useRouter();

  const prevJobStatusesRef = useRef<Record<string, { status: string; isGeneratingScripts?: boolean }>>({});

  const applyJobs = useCallback((newJobs: MyJob[]) => {
    setJobs(newJobs);
    const prev = prevJobStatusesRef.current;
    const prevUuids = Object.keys(prev);
    const newUuids = new Set(newJobs.map((j) => j.job_uuid));
    const jobRemoved = prevUuids.some((uuid) => !newUuids.has(uuid));
    const changed = jobRemoved || newJobs.some((j) =>
      prev[j.job_uuid] !== undefined && (
        prev[j.job_uuid].status !== j.status ||
        prev[j.job_uuid].isGeneratingScripts !== j.is_generating_scripts
      )
    );
    if (changed) window.dispatchEvent(new CustomEvent("kis-jobs-status-changed"));
    prevJobStatusesRef.current = Object.fromEntries(
      newJobs.map((j) => [j.job_uuid, { status: j.status, isGeneratingScripts: j.is_generating_scripts }])
    );
  }, []);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch("/api/jobs/my?limit=20", { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      applyJobs(data.jobs ?? []);
    } catch {
      // silently ignore
    }
  }, [applyJobs]);

  // BroadcastChannel — sync job state across windows/tabs of the same browser
  useEffect(() => {
    const bc = new BroadcastChannel("kis-jobs");
    bc.onmessage = (e) => { if (e.data?.jobs) applyJobs(e.data.jobs); };
    return () => bc.close();
  }, [applyJobs]);

  // SSE connection — opens only when tab is visible, closes when hidden
  // This prevents exhausting the browser's 6-connection-per-origin limit
  // when many tabs are open simultaneously.
  useEffect(() => {
    let es: EventSource | null = null;
    let fallbackPoll: ReturnType<typeof setInterval> | null = null;
    let errCount = 0;
    const bc = new BroadcastChannel("kis-jobs");

    const sseUrl = process.env.NODE_ENV === "development"
      ? "http://localhost:8000/jobs/stream"
      : "/api/jobs/stream";

    const openSSE = () => {
      if (es) return;
      errCount = 0;
      es = new EventSource(sseUrl, { withCredentials: true });
      es.onmessage = (e) => {
        errCount = 0;
        try {
          const data = JSON.parse(e.data);
          applyJobs(data.jobs ?? []);
          bc.postMessage({ jobs: data.jobs ?? [] });
        } catch { /* ignore parse errors */ }
        if (fallbackPoll) { clearInterval(fallbackPoll); fallbackPoll = null; }
      };
      es.onerror = () => {
        errCount++;
        if (errCount >= 3 && !fallbackPoll) {
          fallbackPoll = setInterval(fetchJobs, 5000);
        }
      };
    };

    const closeSSE = () => {
      if (es) { es.close(); es = null; }
    };

    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        openSSE();
        fetchJobs(); // sofortiger Snapshot beim Tab-Wechsel
      } else {
        closeSSE();
        if (fallbackPoll) { clearInterval(fallbackPoll); fallbackPoll = null; }
      }
    };

    document.addEventListener("visibilitychange", onVisibility);

    // Initial fetch so badge shows immediately before first SSE message arrives
    fetchJobs();
    if (document.visibilityState === "visible") openSSE();

    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      closeSSE();
      bc.close();
      if (fallbackPoll) clearInterval(fallbackPoll);
    };
  }, [applyJobs, fetchJobs]);

  // Refresh immediately when any tool page starts or cancels a job
  useEffect(() => {
    const handler = () => fetchJobs();
    window.addEventListener("kis-jobs-changed", handler);
    return () => window.removeEventListener("kis-jobs-changed", handler);
  }, [fetchJobs]);

  // Refresh when tab becomes visible (browser throttles SSE in background tabs)
  useEffect(() => {
    const handler = () => { if (!document.hidden) fetchJobs(); };
    document.addEventListener("visibilitychange", handler);
    return () => document.removeEventListener("visibilitychange", handler);
  }, [fetchJobs]);

  // Refresh jobs when panel opens
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    fetchJobs().finally(() => setLoading(false));
  }, [open, fetchJobs]);

  // Close on outside click/tap
  useEffect(() => {
    if (!open) return;
    const handler = (e: PointerEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, [open]);

  const handleMouseEnter = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    setOpen(true);
  };

  const handleMouseLeave = () => {
    hoverTimeoutRef.current = setTimeout(() => setOpen(false), 150);
  };

  const handleButtonClick = () => {
    if (open) {
      setOpen(false);
      router.push("/my-jobs");
    } else {
      setOpen(true);
    }
  };

  const attentionCount = jobs.filter((j) => needsAttention(j.status)).length;

  const handleDownload = (e: React.MouseEvent, job: MyJob) => {
    e.stopPropagation();
    const a = document.createElement("a");
    a.href = `/api/jobs/${job.job_uuid}/download`;
    if (job.result_filename) a.download = job.result_filename;
    a.click();
  };

  const handleDownloadBundle = async (e: React.MouseEvent, job: MyJob) => {
    e.stopPropagation();
    if (bundleDownloading) return;
    setBundleDownloading(job.job_uuid);
    try {
      const res = await fetch(`/api/jobs/${job.job_uuid}/bundle`, { credentials: "include" });
      if (!res.ok) throw new Error("Bundle-Download fehlgeschlagen");
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition");
      let filename = "bundle.zip";
      if (disposition) {
        const m = disposition.match(/filename="?([^";\n]+)"?/i);
        if (m) filename = m[1].trim();
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      console.error("Bundle download failed");
    } finally {
      setBundleDownloading(null);
    }
  };

  const handleCancel = async (e: React.MouseEvent, job: MyJob) => {
    e.stopPropagation();
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

  const handleRetry = async (e: React.MouseEvent, job: MyJob) => {
    e.stopPropagation();
    setRetrying(job.job_uuid);
    try {
      const res = await fetch(`/api/jobs/${job.job_uuid}/retry`, { method: "POST", credentials: "include" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Wiederholen fehlgeschlagen");
        return;
      }
      window.dispatchEvent(new Event("kis-jobs-status-changed"));
      setOpen(false);
      router.push("/my-jobs");
    } finally {
      setRetrying(null);
    }
  };

  const handleJobClick = (_job: MyJob) => {
    setOpen(false);
    router.push("/my-jobs");
  };

  return (
    <div className="relative" ref={panelRef} onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave}>
      <button
        onClick={handleButtonClick}
        onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open("/my-jobs", "_blank"); } }}
        aria-label="Meine Jobs"
        className="relative flex items-center gap-1.5 px-3 py-1.5 text-sm text-white/80 hover:text-white rounded-full transition-colors"
        style={{ backgroundColor: "rgba(255,255,255,0.10)" }}
        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.18)")}
        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.10)")}
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <span className="text-sm font-medium">Jobs</span>
        {attentionCount > 0 && (
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-white text-[#004261] text-[9px] font-bold rounded-full flex items-center justify-center shadow">
            {attentionCount}
          </span>
        )}
      </button>

      {open && (
        <>
          {/* Mobile backdrop */}
          <div className="sm:hidden fixed inset-0 bg-black/40 z-40" onClick={() => setOpen(false)} />
        </>
      )}
      {open && (
        <div className="
          fixed inset-x-0 bottom-0 z-50 rounded-t-xl
          sm:absolute sm:inset-auto sm:right-0 sm:top-full sm:bottom-auto sm:mt-2 sm:w-80 sm:rounded-xl
          shadow-xl overflow-hidden
        " style={{ backgroundColor: "var(--bg)", border: "1px solid var(--border)" }}>
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-800">Meine Jobs</span>
            {loading && (
              <div className="w-3.5 h-3.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            )}
          </div>

          <div className="px-4 py-2 border-b" style={{ borderColor: "var(--border)" }}>
            <p className="text-xs text-[#004261]">
              Downloads 7 Tage verfügbar. Es werden nur die letzten 20 Jobs gespeichert.
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
                    <li
                      key={job.job_uuid}
                      onClick={() => handleJobClick(job)}
                      className={`px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors ${expired ? "opacity-50" : ""}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5 mb-0.5">
                            <span
                              className="w-2 h-2 rounded-full flex-shrink-0"
                              style={{ backgroundColor: getToolConfigByJobTool(job.tool).color }}
                            />
                            <p className="text-xs font-medium text-gray-800 truncate">{job.tool_label}</p>
                          </div>
                          <p className="text-xs text-gray-400 truncate mt-0.5">{job.original_filename}</p>
                          {job.tts_params?.voice_label || job.tts_params?.provider ? (
                            <p className="text-xs text-gray-400 truncate mt-0.5">
                              {job.tts_params.provider === "kokoro" ? "Kokoro TTS" : job.tts_params.provider === "elevenlabs" ? "ElevenLabs" : job.tts_params.provider}
                              {job.tts_params.voice_label ? ` · ${job.tts_params.voice_label}` : ""}
                            </p>
                          ) : null}
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
                          {!expired && job.status === "success" && job.has_download && (
                            <div className="mt-1.5 flex flex-row flex-wrap gap-2">
                              <button
                                onClick={(e) => handleDownload(e, job)}
                                className="text-xs text-[#004261] hover:underline flex items-center gap-1"
                              >
                                <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                                {SCREENCAST_RENDER_TOOLS.has(job.tool) || job.tool === "screencast_translate" ? "MP4" : job.tool === "image_generate" ? (job.result_filename?.endsWith(".json") ? "ZIP" : "PNG") : job.tool === "image_edit" ? "PNG" : job.tool === "image_analyze" ? "TXT" : job.tool === "tts" ? "MP3" : (job.tool === "transcription" || job.tool === "translation" || job.tool === "summary" || job.tool === "video_dubbing") ? (job.result_filename?.split(".").pop()?.toUpperCase() ?? "Datei") : "Datei"}
                              </button>
                              {(SCREENCAST_RENDER_TOOLS.has(job.tool) || job.tool === "screencast_translate") && (
                                <button
                                  onClick={(e) => handleDownloadBundle(e, job)}
                                  disabled={bundleDownloading === job.job_uuid}
                                  className="text-xs text-[#004261] hover:underline flex items-center gap-1 disabled:opacity-60 disabled:cursor-not-allowed"
                                >
                                  {bundleDownloading === job.job_uuid ? (
                                    <svg className="h-3 w-3 shrink-0 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                                    </svg>
                                  ) : (
                                    <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                    </svg>
                                  )}
                                  {bundleDownloading === job.job_uuid ? "Wird erstellt…" : "Alles herunterladen (ZIP)"}
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="flex flex-col items-end gap-1.5 shrink-0">
                          <StatusBadge status={job.status} expired={expired} isGeneratingScripts={job.is_generating_scripts} />
                          {isActive(job.status) && (
                            <button
                              onClick={(e) => handleCancel(e, job)}
                              disabled={cancelling === job.job_uuid}
                              className="text-xs text-red-500 hover:underline disabled:opacity-50"
                            >
                              {cancelling === job.job_uuid ? "..." : "Abbrechen"}
                            </button>
                          )}
                          {(job.tool === "tts" || job.tool === "screencast_translate" || job.tool === "screencast_render" || job.tool === "screencast_demo_render") && job.status === "failed" && (
                            <button
                              onClick={(e) => handleRetry(e, job)}
                              disabled={retrying === job.job_uuid}
                              className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                            >
                              {retrying === job.job_uuid ? "..." : "Wiederholen"}
                            </button>
                          )}
                        </div>
                      </div>
                      {job.status === "awaiting_user" && (job.tool === "screencast_translate" || job.tool === "screencast_demo_render") && (
                        <div className="mt-2">
                          {job.is_generating_scripts ? (
                            <span className="inline-flex items-center gap-1.5 text-xs text-gray-500 bg-gray-50 border border-gray-200 px-2.5 py-1 rounded-full">
                              <svg className="w-3 h-3 animate-spin shrink-0" viewBox="0 0 24 24" fill="none">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
                              </svg>
                              Skripte werden generiert…
                            </span>
                          ) : (
                            <a
                              href={job.tool === "screencast_demo_render" ? `/screencast-demo?resume=${job.job_uuid}` : `/screencast?resume=${job.job_uuid}`}
                              onClick={(e) => { e.stopPropagation(); setOpen(false); }}
                              className="inline-flex items-center gap-1 text-xs text-orange-700 bg-orange-50 hover:bg-orange-100 border border-orange-200 px-2.5 py-1 rounded-full"
                            >
                              {job.tool === "screencast_demo_render" ? "Demo fortsetzen →" : "Screencast fortsetzen →"}
                            </a>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="px-4 py-2.5 border-t border-gray-100 text-center">
            <Link
              href="/my-jobs"
              onClick={() => setOpen(false)}
              className="text-xs text-[#004261] hover:underline"
            >
              Zur Übersicht
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
