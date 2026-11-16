"use client";

import type { MouseEvent, ReactNode } from "react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import StatusMark from "@/components/ui/StatusMark";
import { jobStatusDisplay } from "@/lib/jobStatusDisplay";
import { formatElapsed, toMs } from "@/lib/format";
import { openJumps, resumeHref as resumeHrefFor } from "./_jobJump";
import { canRetry as canRetryJob, downloadFormat, isExpired, isScreencast, type MyJob } from "./_myJob";
import { JobSources } from "./JobSources";

function useTimeAgo() {
  const t = useTranslations("myJobs.relativeTime");
  return (dateStr: string): string => {
    const diff = Math.floor((Date.now() - toMs(dateStr)) / 1000);
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

// Same look as the resume button in the status badge, every job action reads as a button.
const aktionsKnopf = "btn-primary inline-flex text-xs font-medium px-2.5 py-1 rounded-md";
const oeffnenLink = "inline-flex items-center gap-1 text-xs text-kb-dark bg-kb20 border border-kb60 hover:outline-2 hover:outline-kb-dark transition-colors px-2.5 py-1 rounded-full";

function StatusBadge({ status, expired, isGeneratingScripts, resumeHref, onResume }: { status: MyJob["status"]; expired: boolean; isGeneratingScripts?: boolean; resumeHref?: string; onResume?: (e: MouseEvent) => void }) {
  const t = useTranslations("myJobs.status");
  const anzeige = jobStatusDisplay(status, { expired, isGeneratingScripts });

  // Resuming is an action, not a state, and therefore gets a button.
  if (anzeige.kind === "action") {
    if (resumeHref)
      return (
        <a href={resumeHref} onClick={onResume} className={aktionsKnopf}>
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

function DownloadLink({ onClick, children }: { onClick: (e: MouseEvent) => void; children: ReactNode }) {
  return (
    <button onClick={onClick} className="download-link text-xs text-kb hover:underline flex items-center gap-1">
      <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      {children}
    </button>
  );
}

function downloadFile(e: MouseEvent, job: MyJob) {
  e.stopPropagation();
  const a = document.createElement("a");
  a.href = `/api/jobs/${job.job_uuid}/download`;
  if (job.result_filename) a.download = job.result_filename;
  a.click();
}

function downloadDocx(e: MouseEvent, job: MyJob) {
  e.stopPropagation();
  const a = document.createElement("a");
  a.href = `/api/jobs/${job.job_uuid}/docx`;
  if (job.result_filename) a.download = job.result_filename.replace(/\.[^.]+$/, "") + ".docx";
  a.click();
}

function downloadBundle(e: MouseEvent, job: MyJob) {
  e.stopPropagation();
  // Direct navigation — browser handles the download natively (instant start)
  const a = document.createElement("a");
  a.href = `/api/jobs/${job.job_uuid}/bundle`;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/** One job in the panel under the header button. */
export default function JobsPanelRow({ job, retrying, onRetry, onOpen, onClose }: {
  job: MyJob;
  retrying: boolean;
  onRetry: (e: MouseEvent, job: MyJob) => void;
  /** A click on the row leads to the full list. */
  onOpen: () => void;
  /** Closes the panel, a link inside the row then leads on by itself. */
  onClose: () => void;
}) {
  const tActions = useTranslations("myJobs.actions");
  const tArtifacts = useTranslations("myJobs.artifacts");
  const tShort = useTranslations("myJobs.timingShort");
  const timeAgo = useTimeAgo();

  const expired = isExpired(job);
  const resumeHref = resumeHrefFor(job);
  const canRetry = canRetryJob(job);
  const followLink = (e: MouseEvent) => { e.stopPropagation(); onClose(); };

  return (
    <li
      onClick={onOpen}
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
          {!expired && job.status === "success" && job.has_download && job.tool !== "pages" && (
            <div className="mt-1.5 flex flex-row flex-wrap gap-2">
              <DownloadLink onClick={(e) => downloadFile(e, job)}>
                {downloadFormat(job) ?? tArtifacts("fallbackFile")}
              </DownloadLink>
              {job.has_docx && (
                <DownloadLink onClick={(e) => downloadDocx(e, job)}>
                  DOCX
                </DownloadLink>
              )}
              {isScreencast(job) && (
                <DownloadLink onClick={(e) => downloadBundle(e, job)}>
                  {tArtifacts("downloadAllZip")}
                </DownloadLink>
              )}
            </div>
          )}
        </div>
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <StatusBadge
            status={job.status}
            expired={expired}
            isGeneratingScripts={job.is_generating_scripts}
            resumeHref={resumeHref}
            onResume={followLink}
          />
          {canRetry && (
            <button
              onClick={(e) => onRetry(e, job)}
              disabled={retrying}
              className={`${aktionsKnopf} disabled:opacity-50`}
            >
              {retrying ? "..." : tActions(job.status === "paused" ? "continue" : "retry")}
            </button>
          )}
          {/* A failed job with its own page continues there, the badge only shows the state. */}
          {!canRetry && !expired && job.status === "failed" && resumeHref && (
            <a href={resumeHref} onClick={followLink} className={aktionsKnopf}>
              {tActions("retry")}
            </a>
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
      {/* "Resume" now sits in the status badge, only open remains here. */}
      {openJumps(job).map((jump) => (
        <div key={jump.label} className="mt-2">
          <a href={jump.href} onClick={followLink} className={oeffnenLink}>
            {tArtifacts(jump.label)}
          </a>
        </div>
      ))}
    </li>
  );
}
