import { useTranslations } from "next-intl";
import { DownloadSimple } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { openJumps } from "@/components/jobs/_jobJump";
import { downloadFormat } from "@/components/jobs/_myJob";
import { triggerUrlDownload } from "@/lib/download";
import { SCREENCAST_RENDER_TOOLS, type MyJob } from "../_types";


interface Download {
  href: string;
  filename?: string;
  label: string;
}

// The file name and the link text a tool falls back to when the job carries no result name.
const DEFAULTS: Record<string, { name: string; label?: string }> = {
  podcast: { name: "podcast.mp3", label: "MP3" },
  praesentation: { name: "praesentation.pptx", label: "PPTX" },
  summary: { name: "zusammenfassung.md", label: "MD" },
};
// The tools whose row keeps the narrow gap.
const TIGHT = new Set(["podcast", "praesentation", "pages", "summary", "translation", "tts", "transcription"]);
// These tools never offer the Word file, even when one exists.
const NO_DOCX = new Set(["podcast", "praesentation", "translation", "tts", "transcription"]);

/** The files a finished job hands out, a page lives in its editor and has none. */
function downloadsOf(job: MyJob, fallbackLabel: string): Download[] {
  if (job.tool === "pages" || job.status !== "success" || !job.has_download) return [];
  const fallback = DEFAULTS[job.tool] ?? { name: "download" };
  const filename = job.tool === "tts"
    ? `${job.original_filename.replace(/\.[^.]+$/, "") || "tts"}_audio.mp3`
    : job.result_filename || fallback.name;
  const list: Download[] = [{
    href: `/api/jobs/${job.job_uuid}/download`,
    filename,
    label: downloadFormat(job) ?? fallback.label ?? fallbackLabel,
  }];
  if (job.has_docx && !NO_DOCX.has(job.tool)) {
    list.push({
      href: `/api/jobs/${job.job_uuid}/docx`,
      filename: (job.result_filename || fallback.name).replace(/\.[^.]+$/, "") + ".docx",
      label: "DOCX",
    });
  }
  return list;
}

function DownloadChip({ href, filename, label }: Download) {
  return (
    <button
      onClick={() => triggerUrlDownload(href, filename)}
      className="download-link text-xs text-kb hover:underline flex items-center gap-1 disabled:opacity-60 disabled:cursor-not-allowed"
    >
      <DownloadSimple size={12} weight="bold" className="shrink-0" />
      {label}
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

/** The finished video and, when the audio run is known, the bundle of everything. */
function ScreencastDownloads({ job, bundleLabel, children }: {
  job: MyJob;
  bundleLabel: string;
  children?: React.ReactNode;
}) {
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
            label={bundleLabel}
          />
        )}
        {children}
      </div>
    </div>
  );
}

export function JobArtifacts({ job }: { job: MyJob }) {
  const t = useTranslations("myJobs.artifacts");
  const downloadAllLabel = t("downloadAllZip");
  // Resume sits in the status badge, only opening remains here.
  const openChips = openJumps(job).map((jump) => <OpenChip key={jump.href} href={jump.href} label={t(jump.label)} />);

  // screencast_translate: single-folder workflow — show artifacts for both phases
  if (job.tool === "screencast_translate") {
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
      return (
        <ScreencastDownloads job={job} bundleLabel={downloadAllLabel}>{openChips}</ScreencastDownloads>
      );
    }

    // During voicing the button leads to the waiting page in the assistant.
    return openChips.length ? <div className="mt-3 flex flex-wrap gap-2 items-center">{openChips}</div> : null;
  }

  // screencast render/auto: show all artifacts (legacy + auto mode)
  if (job.status === "success" && SCREENCAST_RENDER_TOOLS.has(job.tool)) {
    return <ScreencastDownloads job={job} bundleLabel={downloadAllLabel} />;
  }

  // Every other tool: its files, then the way back into the tool.
  const downloads = downloadsOf(job, t("fallbackFile"));
  if (!downloads.length && !openChips.length) return null;
  return (
    <div className={`mt-3 flex flex-wrap ${TIGHT.has(job.tool) ? "gap-2" : "gap-3"} items-center`}>
      {downloads.map((d) => <DownloadChip key={d.href} {...d} />)}
      {openChips}
    </div>
  );
}
