import { Trash } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import { isActive, isExpired, type MyJob } from "../_types";
import { StatusBadge } from "./StatusBadge";
import { TimingInfo } from "./TimingInfo";
import { JobArtifacts } from "./JobArtifacts";


interface JobListItemProps {
  job: MyJob;
  isAdmin: boolean;
  cancelling: string | null;
  retrying: string | null;
  onCancel: (job: MyJob) => void;
  onRetry: (job: MyJob) => void;
  onRequestDelete: (job: MyJob) => void;
}


function providerLabel(provider: string | undefined): string {
  if (provider === "kokoro") return "Kokoro TTS";
  if (provider === "mylab") return "THL myLab";
  if (provider === "elevenlabs") return "ElevenLabs";
  return provider ?? "";
}


export function JobListItem({
  job, isAdmin, cancelling, retrying, onCancel, onRetry, onRequestDelete,
}: JobListItemProps) {
  const expired = isExpired(job);
  const canRetry =
    (job.tool === "tts" || job.tool === "screencast_translate" || job.tool === "screencast_render" || job.tool === "screencast_demo_render")
    && job.status === "failed";

  return (
    <li className={`px-5 py-4 hover:bg-gray-100 transition ${expired ? "opacity-50" : ""}`}>
      <div className="flex items-stretch justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gray-800 mb-0.5">{job.tool_label}</p>
          <p className="text-xs text-gray-400 truncate mt-0.5">{job.original_filename}</p>
          {job.tts_params?.voice_label || job.tts_params?.provider ? (
            <p className="text-xs text-gray-400 mt-0.5">
              {providerLabel(job.tts_params.provider)}
              {job.tts_params.voice_label ? ` · ${job.tts_params.voice_label}` : ""}
            </p>
          ) : null}
          {isAdmin && job.folder_name && (
            <p className="text-xs text-gray-300 font-mono truncate mt-0.5">{job.folder_name}</p>
          )}
          <TimingInfo job={job} isAdmin={isAdmin} />
          {job.status === "failed" && job.error && (
            <p className="text-xs text-red-500 mt-1">{job.error}</p>
          )}
          {!expired && <JobArtifacts job={job} />}
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <StatusBadge status={job.status} expired={expired} isGeneratingScripts={job.is_generating_scripts} />
          {isActive(job.status) && (
            <button
              onClick={() => onCancel(job)}
              disabled={cancelling === job.job_uuid}
              className="text-xs text-red-500 hover:underline disabled:opacity-50"
            >
              {cancelling === job.job_uuid ? "..." : "Abbrechen"}
            </button>
          )}
          {canRetry && (
            <button
              onClick={() => onRetry(job)}
              disabled={retrying === job.job_uuid}
              className="text-xs text-blue-600 hover:underline disabled:opacity-50"
            >
              {retrying === job.job_uuid ? "..." : "Wiederholen"}
            </button>
          )}
          {!isActive(job.status) && (
            <IconButton
              onClick={() => onRequestDelete(job)}
              title="Job löschen"
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
