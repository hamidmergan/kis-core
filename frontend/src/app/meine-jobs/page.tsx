"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";

interface MyJob {
  job_uuid: string;
  tool: string;
  tool_label: string;
  original_filename: string;
  status: "pending" | "running" | "success" | "failed";
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  expires_at: string | null;
  has_download: boolean;
  result_filename: string | null;
}

interface JobDetail {
  result: Record<string, unknown> | null;
  meta: Record<string, unknown> | null;
  download_url: string | null;
}

const SCREENCAST_RENDER_TOOLS = new Set(["screencast_render", "screencast_auto", "screencast_demo_render"]);
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

function formatDuration(ms: number): string {
  const totalSec = Math.round(ms / 1000);
  if (totalSec < 60) return `${totalSec} Sek.`;
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")} Std.`;
  return `${m}:${String(s).padStart(2, "0")} Min.`;
}

function toMs(dateStr: string): number {
  return new Date(dateStr + "Z").getTime();
}

function TimingInfo({ job }: { job: MyJob }) {
  const waitMs = job.started_at ? toMs(job.started_at) - toMs(job.created_at) : null;
  const workMs = job.started_at && job.completed_at ? toMs(job.completed_at) - toMs(job.started_at) : null;

  return (
    <div className="mt-1.5 text-xs text-gray-400 space-y-0.5">
      <p>Eingereicht: {formatDate(job.created_at)}</p>
      {waitMs !== null && (
        <p>Wartezeit: <span className="text-gray-500">{formatDuration(waitMs)}</span></p>
      )}
      {workMs !== null && (
        <p>Bearbeitungszeit: <span className="text-gray-500">{formatDuration(workMs)}</span></p>
      )}
      {job.completed_at && (
        <p>Fertig: {formatDate(job.completed_at)}</p>
      )}
      {job.expires_at && (
        <p>Läuft ab: {formatDate(job.expires_at)}</p>
      )}
    </div>
  );
}

function downloadBlob(data: string, filename: string, mimeType: string) {
  const bytes = Uint8Array.from(atob(data), (c) => c.charCodeAt(0));
  const blob = new Blob([bytes], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadText(text: string, filename: string, mimeType: string) {
  const blob = new Blob([text], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function DownloadButton({ href, filename, label }: { href?: string; filename?: string; label: string }) {
  const handleClick = () => {
    if (!href) return;
    const a = document.createElement("a");
    a.href = href;
    if (filename) a.download = filename;
    a.click();
  };
  return (
    <button
      onClick={handleClick}
      className="text-xs text-[#0066cc] hover:underline text-left"
    >
      {label}
    </button>
  );
}

function JobArtifacts({ job, detail }: { job: MyJob; detail: JobDetail | null }) {
  const router = useRouter();

  // screencast_translate: show PPTX download if available
  if (job.tool === "screencast_translate" && job.status === "success") {
    const fileId = detail?.result?.file_id as string | undefined;
    if (!fileId) return null;
    return (
      <div className="mt-3">
        <DownloadButton
          href={`/api/screencast/file/${fileId}`}
          filename="translated.pptx"
          label="Übersetzte PPTX herunterladen"
        />
      </div>
    );
  }

  // screencast render/auto/demo: show all artifacts
  if (job.status === "success" && SCREENCAST_RENDER_TOOLS.has(job.tool)) {
    const meta = detail?.meta as Record<string, unknown> | null;
    const audioId = meta?.audio_id as string | undefined;
    const audioCount = meta?.audio_count as number | undefined;
    const fileId = meta?.file_id as string | undefined;
    const baseName = job.original_filename.replace(/\.pptx$/i, "") || "screencast";

    let srt: string | undefined;
    let vtt: string | undefined;
    let txt: string | undefined;
    if (meta?.subtitle_b64) {
      try {
        const parsed = JSON.parse(atob(meta.subtitle_b64 as string));
        srt = parsed.srt || undefined;
        vtt = parsed.vtt || undefined;
        txt = parsed.txt || undefined;
      } catch { /* ignore */ }
    }

    return (
      <div className="mt-3 flex flex-wrap gap-2 items-center">
        {job.has_download && (
          <DownloadButton
            href={`/api/jobs/${job.job_uuid}/download`}
            filename={job.result_filename || `${baseName}.mp4`}
            label="MP4 herunterladen"
          />
        )}
        {fileId && (
          <DownloadButton
            href={`/api/screencast/file/${fileId}`}
            filename={`${baseName}_translated.pptx`}
            label="PPTX herunterladen"
          />
        )}
        {srt && (
          <button
            onClick={() => downloadText(srt!, `${baseName}.srt`, "application/x-subrip")}
            className="text-xs text-[#0066cc] hover:underline"
          >
            SRT herunterladen
          </button>
        )}
        {vtt && (
          <button
            onClick={() => downloadText(vtt!, `${baseName}.vtt`, "text/vtt")}
            className="text-xs text-[#0066cc] hover:underline"
          >
            VTT herunterladen
          </button>
        )}
        {txt && (
          <button
            onClick={() => downloadText(txt!, `${baseName}.txt`, "text/plain")}
            className="text-xs text-[#0066cc] hover:underline"
          >
            TXT herunterladen
          </button>
        )}
        {audioId && audioCount && audioCount > 0 && (
          <SlideAudioSection audioId={audioId} audioCount={audioCount} baseName={baseName} />
        )}
      </div>
    );
  }

  // TTS: show MP3 download
  if (job.tool === "tts" && job.status === "success" && job.has_download) {
    return (
      <div className="mt-3">
        <DownloadButton
          href={`/api/jobs/${job.job_uuid}/download`}
          filename={job.result_filename || "tts_output.mp3"}
          label="MP3 herunterladen"
        />
      </div>
    );
  }

  // video_dubbing: show video + subtitles
  if (job.tool === "video_dubbing" && job.status === "success") {
    const meta = detail?.meta as Record<string, unknown> | null;
    const srt = meta?.srt as string | undefined;
    const vtt = meta?.vtt as string | undefined;
    const txt = meta?.txt as string | undefined;
    const baseName = job.original_filename.replace(/\.(mp4|mp3)$/i, "") || "dubbed";

    return (
      <div className="mt-3 flex flex-wrap gap-2 items-center">
        {job.has_download && (
          <DownloadButton
            href={`/api/jobs/${job.job_uuid}/download`}
            filename={job.result_filename || `${baseName}_dubbed.mp4`}
            label="Video herunterladen"
          />
        )}
        {srt && (
          <button
            onClick={() => downloadText(srt, `${baseName}.srt`, "application/x-subrip")}
            className="text-xs text-[#0066cc] hover:underline"
          >
            SRT herunterladen
          </button>
        )}
        {vtt && (
          <button
            onClick={() => downloadText(vtt, `${baseName}.vtt`, "text/vtt")}
            className="text-xs text-[#0066cc] hover:underline"
          >
            VTT herunterladen
          </button>
        )}
        {txt && (
          <button
            onClick={() => downloadText(txt, `${baseName}.txt`, "text/plain")}
            className="text-xs text-[#0066cc] hover:underline"
          >
            TXT herunterladen
          </button>
        )}
      </div>
    );
  }

  // Generic fallback: any job with a downloadable result
  if (job.status === "success" && job.has_download) {
    return (
      <div className="mt-3">
        <DownloadButton
          href={`/api/jobs/${job.job_uuid}/download`}
          filename={job.result_filename || "download"}
          label="Herunterladen"
        />
      </div>
    );
  }

  return null;
}

function SlideAudioSection({ audioId, audioCount, baseName }: { audioId: string; audioCount: number; baseName: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="w-full mt-1">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="text-xs text-gray-500 hover:text-gray-700 underline"
      >
        {expanded ? "▲" : "▼"} Folien-Audios ({audioCount} Dateien)
      </button>
      {expanded && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {Array.from({ length: audioCount }, (_, i) => (
            <DownloadButton
              key={i}
              href={`/api/screencast/audio/${audioId}/${i}`}
              filename={`${baseName}_folie_${i + 1}.mp3`}
              label={`Folie ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function MeineJobsPage() {
  const [jobs, setJobs] = useState<MyJob[]>([]);
  const [details, setDetails] = useState<Record<string, JobDetail>>({});
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
        const cutoff = Date.now() - 12 * 60 * 60 * 1000;
        const recent: MyJob[] = (data.jobs ?? []).filter(
          (j: MyJob) => new Date(j.created_at + "Z").getTime() >= cutoff
        );
        setJobs(recent);

        // Fetch detail for completed jobs
        const detailJobs = recent.filter(
          (j) => j.status === "success"
        );
        Promise.all(
          detailJobs.map((j) =>
            fetch(`/api/jobs/${j.job_uuid}`, { credentials: "include" })
              .then((r) => r.json())
              .then((d) => ({ uuid: j.job_uuid, detail: { result: d.result, meta: d.meta, download_url: d.download_url } }))
              .catch(() => null)
          )
        ).then((results) => {
          const map: Record<string, JobDetail> = {};
          for (const r of results) {
            if (r) map[r.uuid] = r.detail;
          }
          setDetails(map);
        });
      })
      .finally(() => setLoading(false));
  }, [router]);

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
        <h2 className="text-lg font-semibold text-gray-800 mb-1">Meine Jobs (letzte 12 Stunden)</h2>
        <p className="text-sm text-gray-500 mb-6">
          Fertige Downloads sind 12 Stunden verfügbar. Ältere Dateien werden automatisch entfernt.
        </p>

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : jobs.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-16">Keine Jobs in den letzten 12 Stunden</p>
        ) : (
          <ul className="divide-y divide-gray-100 border border-gray-200 rounded-xl overflow-hidden">
            {jobs.map((job) => {
              const expired = isExpired(job);
              const detail = details[job.job_uuid] ?? null;
              return (
                <li key={job.job_uuid} className={`px-5 py-4 bg-white ${expired ? "opacity-50" : "hover:bg-gray-50"}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-800">{job.tool_label}</p>
                      <p className="text-xs text-gray-400 truncate mt-0.5">{job.original_filename}</p>
                      <TimingInfo job={job} />
                      {job.status === "failed" && job.error && (
                        <p className="text-xs text-red-500 mt-1">{job.error}</p>
                      )}
                      {!expired && <JobArtifacts job={job} detail={detail} />}
                    </div>
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <StatusBadge status={job.status} expired={expired} />
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
