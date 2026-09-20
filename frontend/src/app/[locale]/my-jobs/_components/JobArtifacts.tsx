import { useState } from "react";
import { useTranslations } from "next-intl";
import { DownloadSimple } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { SCREENCAST_RENDER_TOOLS, type MyJob } from "../_types";
import { podcastJumpHref, podcastJumpKind } from "@/components/jobs/_podcastJump";
import { screencastJumpHref, screencastJumpKind } from "@/components/jobs/_screencastJump";


function DownloadChip({ onClick, href, filename, label }: { onClick?: () => void | Promise<void>; href?: string; filename?: string; label: string }) {
  const t = useTranslations("myJobs.artifacts");
  const [busy, setBusy] = useState(false);
  const handleClick = async () => {
    if (busy) return;
    if (onClick) {
      setBusy(true);
      try { await onClick(); } finally { setBusy(false); }
      return;
    }
    if (!href) return;
    const a = document.createElement("a");
    a.href = href;
    if (filename) a.download = filename;
    a.click();
  };
  return (
    <button
      onClick={handleClick}
      disabled={busy}
      className="download-link text-xs text-kb hover:underline flex items-center gap-1 disabled:opacity-60 disabled:cursor-not-allowed"
    >
      {busy ? (
        <Spinner size="sm" />
      ) : (
        <DownloadSimple size={12} weight="bold" className="shrink-0" />
      )}
      {busy ? t("creating") : label}
    </button>
  );
}

/** The way back into the tool that made the job, for screencast and podcast alike. */
function OpenChip({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="inline-flex items-center gap-1 text-xs text-kb-dark bg-kb20 border border-kb60 hover:outline-2 hover:outline-kb-dark transition-colors px-2.5 py-1 rounded-full"
    >
      {label}
    </a>
  );
}

function DisabledChip({ label }: { label: string }) {
  return (
    <span className="text-xs text-muted-soft flex items-center gap-1 cursor-not-allowed select-none">
      <DownloadSimple size={12} weight="bold" className="shrink-0" />
      {label}
    </span>
  );
}


export function JobArtifacts({ job }: { job: MyJob }) {
  const t = useTranslations("myJobs.artifacts");
  const downloadAllLabel = t("downloadAllZip");

  // screencast_translate: single-folder workflow — show artifacts for both phases
  if (job.tool === "screencast_translate") {
    // Resume now sits in the status badge, only opening remains here.
    const sprung = screencastJumpKind(job);
    const sprungChip = sprung === "open" && (
      <OpenChip href={screencastJumpHref(job.job_uuid)} label={t("openScreencast")} />
    );

    if (job.status === "awaiting_user") {
      // Without running scripts nothing stays here, the badge leads on.
      if (!job.is_generating_scripts) return null;
      return (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap gap-2 items-center">
            <DisabledChip label="MP4" />
            <DisabledChip label={downloadAllLabel} />
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <span className="inline-flex items-center gap-1.5 text-xs text-muted bg-surface border border-border-soft px-2.5 py-1 rounded-full">
              <Spinner size="sm" />
              {t("generatingScripts")}
            </span>
          </div>
        </div>
      );
    }

    if (job.status === "success") {
      const meta = (job.meta ?? null) as Record<string, unknown> | null;
      const audioId = meta?.audio_id as string | undefined;
      return (
        <div className="mt-3">
          <div className="flex flex-wrap gap-2 items-center">
            {job.has_download && (
              <DownloadChip
                href={`/api/jobs/${job.job_uuid}/download`}
                filename={job.result_filename ?? undefined}
                label="MP4"
              />
            )}
            {audioId && (
              <DownloadChip
                href={`/api/jobs/${audioId}/bundle`}
                label={downloadAllLabel}
              />
            )}
            {sprungChip}
          </div>
        </div>
      );
    }

    // During voicing the button leads to the waiting page in the assistant.
    return sprungChip ? <div className="mt-3 flex flex-wrap gap-2 items-center">{sprungChip}</div> : null;
  }

  // screencast render/auto: show all artifacts (legacy + auto mode)
  if (job.status === "success" && SCREENCAST_RENDER_TOOLS.has(job.tool)) {
    const meta = (job.meta ?? null) as Record<string, unknown> | null;
    const audioId = meta?.audio_id as string | undefined;

    return (
      <div className="mt-3">
        <div className="flex flex-wrap gap-2 items-center">
          {job.has_download && (
            <DownloadChip
              href={`/api/jobs/${job.job_uuid}/download`}
              filename={job.result_filename ?? undefined}
              label="MP4"
            />
          )}
          {audioId && (
            <DownloadChip
              href={`/api/jobs/${audioId}/bundle`}
              label={downloadAllLabel}
            />
          )}
        </div>
      </div>
    );
  }

  // Podcast: the finished MP3 plus the way back into the tool, resuming sits in the badge.
  if (job.tool === "podcast") {
    const sprung = podcastJumpKind(job);
    const laedt = job.status === "success" && job.has_download;
    if (!laedt && sprung !== "open") return null;
    return (
      <div className="mt-3 flex flex-wrap gap-2 items-center">
        {laedt && (
          <DownloadChip
            href={`/api/jobs/${job.job_uuid}/download`}
            filename={job.result_filename || "podcast.mp3"}
            label="MP3"
          />
        )}
        {sprung === "open" && <OpenChip href={podcastJumpHref(job.job_uuid)} label={t("openPodcast")} />}
      </div>
    );
  }

  // TTS: show MP3 download
  if (job.tool === "tts" && job.status === "success" && job.has_download) {
    const baseName = job.original_filename.replace(/\.[^.]+$/, "") || "tts";
    return (
      <div className="mt-3">
        <DownloadChip
          href={`/api/jobs/${job.job_uuid}/download`}
          filename={`${baseName}_audio.mp3`}
          label="MP3"
        />
      </div>
    );
  }

  // Generic fallback: any job with a downloadable result
  if (job.status === "success" && job.has_download) {
    const downloadLabel =
      job.tool === "image_generate" || job.tool === "image_edit"
        ? "PNG"
        : job.tool === "image_analyze"
        ? "TXT"
        : (job.tool === "transcription" || job.tool === "translation" || job.tool === "summary")
        ? (job.result_filename?.split(".").pop()?.toUpperCase() ?? t("fallbackFile"))
        : t("fallbackFile");
    return (
      <div className="mt-3 flex flex-wrap gap-3 items-center">
        <DownloadChip
          href={`/api/jobs/${job.job_uuid}/download`}
          filename={job.result_filename || "download"}
          label={downloadLabel}
        />
        {job.has_docx && (
          <DownloadChip
            href={`/api/jobs/${job.job_uuid}/docx`}
            filename={(job.result_filename || "download").replace(/\.[^.]+$/, "") + ".docx"}
            label="DOCX"
          />
        )}
      </div>
    );
  }

  return null;
}
