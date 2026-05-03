import { useState } from "react";
import { useTranslations } from "next-intl";
import { DownloadSimple } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { SCREENCAST_RENDER_TOOLS, type MyJob } from "../_types";


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
    if (job.status === "awaiting_user") {
      return (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap gap-2 items-center">
            <DisabledChip label="MP4" />
            <DisabledChip label={downloadAllLabel} />
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            {job.is_generating_scripts ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-muted bg-surface border border-border-soft px-2.5 py-1 rounded-full">
                <Spinner size="sm" />
                {t("generatingScripts")}
              </span>
            ) : (
              <a
                href={`/tools/screencast?resume=${job.job_uuid}`}
                className="inline-flex items-center gap-1 text-xs text-warn-strong bg-warn-bg hover:bg-warn-bg border border-warn-border px-2.5 py-1 rounded-full"
              >
                {t("resumeScreencast")}
              </a>
            )}
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
          </div>
        </div>
      );
    }
    return null;
  }

  // screencast_demo_render: same download chip layout when awaiting_user
  if (job.tool === "screencast_demo_render" && job.status === "awaiting_user") {
    return (
      <div className="mt-3 space-y-2">
        <div className="flex flex-wrap gap-2 items-center">
          <DisabledChip label="MP4" />
          <DisabledChip label={downloadAllLabel} />
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          {job.is_generating_scripts ? (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted bg-surface border border-border-soft px-2.5 py-1 rounded-full">
              <Spinner size="xs" />
              {t("generatingScripts")}
            </span>
          ) : (
            <a
              href={`/tools/screencast-demo?resume=${job.job_uuid}`}
              className="inline-flex items-center gap-1 text-xs text-warn-strong bg-warn-bg hover:bg-warn-bg border border-warn-border px-2.5 py-1 rounded-full"
            >
              {t("resumeDemo")}
            </a>
          )}
        </div>
      </div>
    );
  }

  // screencast render/auto/demo: show all artifacts (legacy + auto mode)
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
      <div className="mt-3">
        <DownloadChip
          href={`/api/jobs/${job.job_uuid}/download`}
          filename={job.result_filename || "download"}
          label={downloadLabel}
        />
      </div>
    );
  }

  return null;
}
