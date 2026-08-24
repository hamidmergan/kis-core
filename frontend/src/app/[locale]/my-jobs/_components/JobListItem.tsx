import { useTranslations } from "next-intl";
import { Trash } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import { isActive, isExpired, type MyJob } from "../_types";
import { StatusBadge } from "./StatusBadge";
import { TimingInfo } from "./TimingInfo";
import { JobArtifacts } from "./JobArtifacts";
import { AdminDetails } from "./AdminDetails";
import { screencastJumpHref, screencastJumpKind } from "@/components/jobs/_screencastJump";


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
  const resumeHref = screencastJumpKind(job) === "resume" ? screencastJumpHref(job.job_uuid) : undefined;
  const canRetry =
    (job.tool === "tts" || job.tool === "screencast_translate" || job.tool === "screencast_render")
    && job.status === "failed";

  return (
    <li className={`px-5 py-4 hover:bg-surface transition ${expired ? "opacity-50" : ""}`}>
      <div className="flex items-stretch justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground mb-0.5">{job.tool_label}</p>
          <p className="text-xs text-muted-soft truncate mt-0.5">{job.original_filename}</p>
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
          {job.status === "failed" && job.error && (
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
              <Trash size={13} />
            </IconButton>
          )}
          {canRetry && (
            <button
              onClick={() => onRetry(job)}
              disabled={retrying === job.job_uuid}
              className="text-xs text-info hover:underline disabled:opacity-50"
            >
              {retrying === job.job_uuid ? "..." : t("retry")}
            </button>
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
