import { useTranslations } from "next-intl";
import { Trash, X } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import { isActive, isExpired, type MyJob } from "../_types";
import { StatusBadge } from "./StatusBadge";
import { TimingInfo } from "./TimingInfo";
import { JobArtifacts } from "./JobArtifacts";
import { AdminDetails } from "./AdminDetails";
import { podcastJumpHref, podcastJumpKind } from "@/components/jobs/_podcastJump";
import { praesentationJumpHref, praesentationJumpKind } from "@/components/jobs/_praesentationJump";
import { screencastJumpHref, screencastJumpKind } from "@/components/jobs/_screencastJump";
import { JobSources } from "@/components/jobs/JobSources";


// Same look as the resume button in the status badge, every job action reads as a button.
const aktionsKnopf = "btn-primary inline-flex text-xs font-medium px-2.5 py-1 rounded-md";

interface JobListItemProps {
  job: MyJob;
  isAdmin: boolean;
  cancelling: string | null;
  retrying: string | null;
  onCancel: (job: MyJob) => void;
  onRetry: (job: MyJob) => void;
  onRequestDelete: (job: MyJob) => void;
}



export function JobListItem({
  job, isAdmin, cancelling, retrying, onCancel, onRetry, onRequestDelete,
}: JobListItemProps) {
  const t = useTranslations("myJobs.actions");
  const expired = isExpired(job);
  const resumeHref = screencastJumpKind(job) === "resume"
    ? screencastJumpHref(job.job_uuid)
    : podcastJumpKind(job) === "resume"
      ? podcastJumpHref(job.job_uuid)
      : praesentationJumpKind(job) === "resume"
        ? praesentationJumpHref(job.job_uuid)
        : undefined;
  const canRetry =
    ((job.tool === "tts" || job.tool === "screencast_translate" || job.tool === "screencast_render")
      && (job.status === "failed" || job.status === "paused"))
    // A paused summary resumes where it stopped, a failed one would only fail again.
    || ((job.tool === "summary" || job.tool === "pages") && job.status === "paused");

  return (
    <li className={`px-5 py-4 hover:bg-surface transition ${expired ? "opacity-50" : ""}`}>
      <div className="flex items-stretch justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground mb-0.5">{job.tool_label}</p>
          <JobSources value={job.original_filename} />
          {job.tts_params?.voice_label || job.tts_params?.provider ? (
            <p className="text-xs text-muted-soft mt-0.5">
              {job.tts_params.provider ?? ""}
              {job.tts_params.voice_label ? ` · ${job.tts_params.voice_label}` : ""}
            </p>
          ) : null}
          {isAdmin && job.folder_name && (
            <p className="text-xs text-border font-mono truncate mt-0.5">{job.folder_name}</p>
          )}
          <TimingInfo job={job} isAdmin={isAdmin} />
          {isAdmin && job.meta?.stats && <AdminDetails stats={job.meta.stats} />}
          {(job.status === "failed" || job.status === "paused") && job.error && (
            <p className="text-xs text-error mt-1">{job.error}</p>
          )}
          {!expired && <JobArtifacts job={job} />}
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <StatusBadge status={job.status} expired={expired} isGeneratingScripts={job.is_generating_scripts} resumeHref={resumeHref} />
          {isActive(job.status) && (
            <IconButton
              onClick={() => onCancel(job)}
              disabled={cancelling === job.job_uuid}
              title={t("cancel")}
              className="mt-auto disabled:opacity-50"
            >
              <X size={13} weight="bold" />
            </IconButton>
          )}
          {canRetry && (
            <button
              onClick={() => onRetry(job)}
              disabled={retrying === job.job_uuid}
              className={`${aktionsKnopf} disabled:opacity-50`}
            >
              {retrying === job.job_uuid ? "..." : t(job.status === "paused" ? "continue" : "retry")}
            </button>
          )}
          {/* A failed job with its own page continues there, the badge only shows the state. */}
          {!canRetry && !expired && job.status === "failed" && resumeHref && (
            <a href={resumeHref} className={aktionsKnopf}>
              {t("retry")}
            </a>
          )}
          {!isActive(job.status) && (
            <IconButton
              onClick={() => onRequestDelete(job)}
              title={t("deleteJob")}
              className="mt-auto"
            >
              <Trash size={13} />
            </IconButton>
          )}
        </div>
      </div>
    </li>
  );
}
