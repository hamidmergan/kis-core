"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { usePathname } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { Stack } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { useNavTransition } from "@/components/ui/useNavTransition";
import { EmptyState } from "@/components/ui/EmptyState";
import StatusMark from "@/components/ui/StatusMark";
import { jobStatusDisplay } from "@/lib/jobStatusDisplay";
import { formatElapsed, toMs } from "@/lib/format";
import { hasUnseenDone } from "./_unseen";
import { podcastJumpHref, podcastJumpKind } from "./_podcastJump";
import { praesentationJumpHref, praesentationJumpKind } from "./_praesentationJump";
import { screencastJumpHref, screencastJumpKind } from "./_screencastJump";
import { JobSources } from "./JobSources";

interface MyJob {
  job_uuid: string;
  tool: string;
  tool_label: string;
  original_filename: string;
  status: "pending" | "running" | "success" | "failed" | "awaiting_user" | "queued" | "waiting_retry" | "paused";
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  expires_at: string | null;
  render_queued_at: string | null;
  has_download: boolean;
  has_docx?: boolean;
  result_filename: string | null;
  tts_params?: { voice_id?: string; voice_label?: string; provider?: string } | null;
  is_generating_scripts?: boolean;
}

const SCREENCAST_RENDER_TOOLS = new Set(["screencast_render", "screencast_auto"]);
const LAST_SEEN_KEY = "kis-jobs-last-seen";

const isExpired = (job: MyJob) => job.status === "success" && !job.has_download;

function useTimeAgo() {
  const t = useTranslations("myJobs.relativeTime");
  return (dateStr: string): string => {
    const diff = Math.floor((Date.now() - new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").getTime()) / 1000);
    if (diff < 60) return t("justNow");
    if (diff < 3600) return t("minutes", { n: Math.floor(diff / 60) });
    if (diff < 86400) return t("hours", { n: Math.floor(diff / 3600) });
    return t("days", { n: Math.floor(diff / 86400) });
  };
}

/** Bare digits, no words: the panel rows are narrow. */
const SHORT_ELAPSED = {
  seconds: (n: number) => `${n}s`,
  minutes: (m: number, s: string) => `${m}:${s}`,
  hours: (h: number, m: string, s: string) => `${h}:${m}:${s}`,
};

function formatDurationShort(ms: number): string {
  return formatElapsed(ms, SHORT_ELAPSED);
}

function StatusBadge({ status, expired, isGeneratingScripts, resumeHref, onResume }: { status: MyJob["status"]; expired: boolean; isGeneratingScripts?: boolean; resumeHref?: string; onResume?: (e: React.MouseEvent) => void }) {
  const t = useTranslations("myJobs.status");
  const anzeige = jobStatusDisplay(status, { expired, isGeneratingScripts });

  // Resuming is an action, not a state, and therefore gets a button.
  if (anzeige.kind === "action") {
    if (resumeHref)
      return (
        <a href={resumeHref} onClick={onResume} className="btn-primary inline-flex text-xs font-medium px-2.5 py-1 rounded-md">
          {t(anzeige.key)}
        </a>
      );
    // Without a page to jump to it is only a state, the action sits next to it.
    const ruhend = anzeige.key === "paused" ? "pausedMark" : "awaitingUser";
    return <StatusMark tone="brand" className="text-xs">{t(ruhend)}</StatusMark>;
  }

  return (
    <StatusMark tone={anzeige.tone} pulse={anzeige.pulse} className="text-xs">
      {t(anzeige.key as "expired" | "success" | "failed" | "running" | "queued" | "pending" | "waitingRetry")}
    </StatusMark>
  );
}

export default function JobsPanel() {
  const tHeader = useTranslations("header");
  const tJobs = useTranslations("myJobs");
  const tActions = useTranslations("myJobs.actions");
  const tArtifacts = useTranslations("myJobs.artifacts");
  const tShort = useTranslations("myJobs.timingShort");
  const tPanel = useTranslations("myJobs.panel");
  const timeAgo = useTimeAgo();

  const [open, setOpen] = useState(false);
  const [jobs, setJobs] = useState<MyJob[]>([]);
  const [lastSeen, setLastSeen] = useState<number | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const router = useRouter();
  const { pending: toJobsPending, navigate } = useNavTransition();
  // The button leads to /my-jobs, so it also shows when you are already there.
  const onJobsPage = usePathname().startsWith("/my-jobs");

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

  // The stream only runs in the visible tab, otherwise the 6 connections fill up fast.
  useEffect(() => {
    let es: EventSource | null = null;
    let fallbackPoll: ReturnType<typeof setInterval> | null = null;
    const bc = new BroadcastChannel("kis-jobs");

    // Through the proxy, so every dev server reaches its own backend.
    const sseUrl = "/api/jobs/stream";

    const stopFallback = () => {
      if (fallbackPoll) { clearInterval(fallbackPoll); fallbackPoll = null; }
    };

    const openSSE = () => {
      if (es && es.readyState !== EventSource.CLOSED) return;
      if (es) es.close();
      es = new EventSource(sseUrl, { withCredentials: true });
      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          applyJobs(data.jobs ?? []);
          bc.postMessage({ jobs: data.jobs ?? [] });
        } catch { /* ignore parse errors */ }
        stopFallback();
      };
      // EventSource retries by itself, only a dead connection needs the fallback.
      es.onerror = () => {
        if (es?.readyState !== EventSource.CLOSED || fallbackPoll) return;
        fallbackPoll = setInterval(() => { fetchJobs(); openSSE(); }, 30000);
      };
    };

    const closeSSE = () => {
      if (es) { es.close(); es = null; }
    };

    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        openSSE();
        fetchJobs(); // immediate snapshot on tab switch
      } else {
        closeSSE();
        stopFallback();
      }
    };

    document.addEventListener("visibilitychange", onVisibility);

    // Initial fetch so the dot shows immediately before first SSE message arrives
    fetchJobs();
    if (document.visibilityState === "visible") openSSE();

    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      closeSSE();
      bc.close();
      stopFallback();
    };
  }, [applyJobs, fetchJobs]);

  // Refresh immediately when any tool page starts or cancels a job
  useEffect(() => {
    const handler = () => fetchJobs();
    window.addEventListener("kis-jobs-changed", handler);
    return () => window.removeEventListener("kis-jobs-changed", handler);
  }, [fetchJobs]);

  // Remembers the last look so the dot only reports what is new.
  useEffect(() => {
    const stored = Number(localStorage.getItem(LAST_SEEN_KEY));
    if (stored > 0) { setLastSeen(stored); return; }
    const now = Date.now();
    localStorage.setItem(LAST_SEEN_KEY, String(now));
    setLastSeen(now);
  }, []);

  // Opening marks everything seen, closing catches what finished meanwhile.
  useEffect(() => {
    if (!open) return;
    const markSeen = () => {
      const now = Date.now();
      localStorage.setItem(LAST_SEEN_KEY, String(now));
      setLastSeen(now);
    };
    markSeen();
    return markSeen;
  }, [open]);

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
      navigate(() => router.push("/my-jobs"));
    } else {
      setOpen(true);
    }
  };

  const hasFreshResult = lastSeen !== null && hasUnseenDone(jobs, lastSeen);

  const handleDownload = (e: React.MouseEvent, job: MyJob) => {
    e.stopPropagation();
    const a = document.createElement("a");
    a.href = `/api/jobs/${job.job_uuid}/download`;
    if (job.result_filename) a.download = job.result_filename;
    a.click();
  };

  const handleDownloadDocx = (e: React.MouseEvent, job: MyJob) => {
    e.stopPropagation();
    const a = document.createElement("a");
    a.href = `/api/jobs/${job.job_uuid}/docx`;
    if (job.result_filename) a.download = job.result_filename.replace(/\.[^.]+$/, "") + ".docx";
    a.click();
  };

  const handleDownloadBundle = (e: React.MouseEvent, job: MyJob) => {
    e.stopPropagation();
    // Direct navigation — browser handles the download natively (instant start)
    const a = document.createElement("a");
    a.href = `/api/jobs/${job.job_uuid}/bundle`;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const handleRetry = async (e: React.MouseEvent, job: MyJob) => {
    e.stopPropagation();
    setRetrying(job.job_uuid);
    try {
      const res = await fetch(`/api/jobs/${job.job_uuid}/retry`, { method: "POST", credentials: "include" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || tJobs("retryFailed"));
        return;
      }
      window.dispatchEvent(new Event("kis-jobs-status-changed"));
      setOpen(false);
      navigate(() => router.push("/my-jobs"));
    } finally {
      setRetrying(null);
    }
  };

  const handleJobClick = (_job: MyJob) => {
    setOpen(false);
    navigate(() => router.push("/my-jobs"));
  };

  return (
    <div className="relative" ref={panelRef} onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave}>
      <button
        onClick={handleButtonClick}
        onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open("/my-jobs", "_blank"); } }}
        aria-label={tHeader("jobs")}
        title={tHeader("jobs")}
        aria-current={onJobsPage ? "page" : undefined}
        className={`relative flex items-center justify-center w-10 h-10 sm:w-auto sm:h-9 sm:px-3 sm:gap-1.5 rounded-full btn-on-dark${onJobsPage ? " is-active" : ""}`}
        data-tour="jobs-entry"
      >
        {toJobsPending ? <Spinner size="sm" color="current" /> : <Stack size={17} weight="bold" aria-hidden="true" />}
        <span className="hidden sm:inline text-sm font-medium">{tHeader("jobs")}</span>
        {hasFreshResult && (
          <>
            <span className="absolute top-0 right-0 w-1.5 h-1.5 bg-error rounded-full shadow" aria-hidden="true" />
            <span className="sr-only">{tPanel("newResults")}</span>
          </>
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
        " style={{ backgroundColor: "var(--background)", border: "1px solid var(--border)" }}>
          <div className="px-4 py-3 border-b border-border-soft flex items-center justify-between">
            <span className="text-sm font-semibold text-foreground">{tJobs("title")}</span>
          </div>

          <div className="px-4 py-2 border-b" style={{ borderColor: "var(--border)" }}>
            <p className="text-xs text-kb">
              {tPanel("notice")}
            </p>
          </div>

          <div>
            {jobs.length === 0 ? (
              <EmptyState
                icon={<Stack size={32} weight="bold" />}
                text={tPanel("empty")}
              />
            ) : (
              <ul className="divide-y divide-border-soft">
                {jobs.slice(0, 3).map((job) => {
                  const expired = isExpired(job);
                  return (
                    <li
                      key={job.job_uuid}
                      onClick={() => handleJobClick(job)}
                      className={`px-4 py-3 cursor-pointer hover:bg-surface transition ${expired ? "opacity-50" : ""}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-foreground truncate mb-0.5">{job.tool_label}</p>
                          <JobSources value={job.original_filename} />
                          {job.tts_params?.voice_label || job.tts_params?.provider ? (
                            <p className="text-xs text-muted-soft truncate mt-0.5">
                              {job.tts_params.provider}
                              {job.tts_params.voice_label ? ` · ${job.tts_params.voice_label}` : ""}
                            </p>
                          ) : null}
                          <p className="text-xs text-muted-soft mt-0.5">{timeAgo(job.created_at)}</p>
                          {(job.started_at || job.completed_at) && (
                            <p className="text-xs text-border mt-0.5">
                              {job.started_at && (
                                <>{tShort("wait")} {formatDurationShort(toMs(job.started_at) - toMs(job.created_at))}</>
                              )}
                              {job.started_at && job.completed_at && (
                                <> · {tShort("work")} {formatDurationShort(toMs(job.completed_at) - toMs(job.started_at))}</>
                              )}
                            </p>
                          )}
                          {job.status === "failed" && job.error && (
                            <p className="text-xs text-error mt-1 line-clamp-2">{job.error}</p>
                          )}
                          {!expired && job.status === "success" && job.has_download && (
                            <div className="mt-1.5 flex flex-row flex-wrap gap-2">
                              <button
                                onClick={(e) => handleDownload(e, job)}
                                className="download-link text-xs text-kb hover:underline flex items-center gap-1"
                              >
                                <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                                {SCREENCAST_RENDER_TOOLS.has(job.tool) || job.tool === "screencast_translate" ? "MP4" : job.tool === "image_generate" ? "PNG" : job.tool === "image_edit" ? "PNG" : job.tool === "image_analyze" ? "TXT" : job.tool === "tts" ? "MP3" : (job.tool === "transcription" || job.tool === "translation" || job.tool === "summary") ? (job.result_filename?.split(".").pop()?.toUpperCase() ?? tArtifacts("fallbackFile")) : tArtifacts("fallbackFile")}
                              </button>
                              {job.has_docx && (
                                <button
                                  onClick={(e) => handleDownloadDocx(e, job)}
                                  className="download-link text-xs text-kb hover:underline flex items-center gap-1"
                                >
                                  <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                  </svg>
                                  DOCX
                                </button>
                              )}
                              {(SCREENCAST_RENDER_TOOLS.has(job.tool) || job.tool === "screencast_translate") && (
                                <button
                                  onClick={(e) => handleDownloadBundle(e, job)}
                                  className="download-link text-xs text-kb hover:underline flex items-center gap-1"
                                >
                                  <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                  </svg>
                                  {tArtifacts("downloadAllZip")}
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="flex flex-col items-end gap-1.5 shrink-0">
                          <StatusBadge
                            status={job.status}
                            expired={expired}
                            isGeneratingScripts={job.is_generating_scripts}
                            resumeHref={
                              screencastJumpKind(job) === "resume"
                                ? screencastJumpHref(job.job_uuid)
                                : podcastJumpKind(job) === "resume"
                                  ? podcastJumpHref(job.job_uuid)
                                  : praesentationJumpKind(job) === "resume"
                                    ? praesentationJumpHref(job.job_uuid)
                                    : undefined
                            }
                            onResume={(e) => { e.stopPropagation(); setOpen(false); }}
                          />
                          {(((job.tool === "tts" || job.tool === "screencast_translate" || job.tool === "screencast_render") && (job.status === "failed" || job.status === "paused"))
                            || (job.tool === "summary" && job.status === "paused")) && (
                            <button
                              onClick={(e) => handleRetry(e, job)}
                              disabled={retrying === job.job_uuid}
                              className="text-xs text-info hover:underline disabled:opacity-50"
                            >
                              {retrying === job.job_uuid ? "..." : tActions(job.status === "paused" ? "continue" : "retry")}
                            </button>
                          )}
                        </div>
                      </div>
                      {job.status === "awaiting_user" && job.tool === "screencast_translate" && job.is_generating_scripts && (
                        <div className="mt-2">
                          <span className="inline-flex items-center gap-1.5 text-xs text-muted bg-surface border border-border-soft px-2.5 py-1 rounded-full">
                            <Spinner size="sm" />
                            {tArtifacts("generatingScripts")}
                          </span>
                        </div>
                      )}
                      {/* "Fortsetzen" sitzt jetzt im Status-Abzeichen, hier bleibt nur das Oeffnen. */}
                      {podcastJumpKind(job) === "open" && (
                        <div className="mt-2">
                          <a
                            href={podcastJumpHref(job.job_uuid)}
                            onClick={(e) => { e.stopPropagation(); setOpen(false); }}
                            className="inline-flex items-center gap-1 text-xs text-kb-dark bg-kb20 border border-kb60 hover:outline-2 hover:outline-kb-dark transition-colors px-2.5 py-1 rounded-full"
                          >
                            {tArtifacts("openPodcast")}
                          </a>
                        </div>
                      )}
                      {praesentationJumpKind(job) === "open" && (
                        <div className="mt-2">
                          <a
                            href={praesentationJumpHref(job.job_uuid)}
                            onClick={(e) => { e.stopPropagation(); setOpen(false); }}
                            className="inline-flex items-center gap-1 text-xs text-kb-dark bg-kb20 border border-kb60 hover:outline-2 hover:outline-kb-dark transition-colors px-2.5 py-1 rounded-full"
                          >
                            {tArtifacts("openPraesentation")}
                          </a>
                        </div>
                      )}
                      {screencastJumpKind(job) === "open" && (
                        <div className="mt-2">
                          <a
                            href={screencastJumpHref(job.job_uuid)}
                            onClick={(e) => { e.stopPropagation(); setOpen(false); }}
                            className="inline-flex items-center gap-1 text-xs text-kb-dark bg-kb20 border border-kb60 hover:outline-2 hover:outline-kb-dark transition-colors px-2.5 py-1 rounded-full"
                          >
                            {tArtifacts("openScreencast")}
                          </a>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="px-4 py-2.5 border-t border-border-soft text-center">
            <Link
              href="/my-jobs"
              onClick={() => setOpen(false)}
              className="text-xs text-kb hover:underline"
            >
              {tPanel("viewAll")}
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
