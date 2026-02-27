"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

interface StorageInfo {
  video: { count: number; limit: number };
  general: { count: number; limit: number };
}

const LIMIT = 10;

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
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [storage, setStorage] = useState<StorageInfo | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const router = useRouter();

  // Debounce q and reset offset at the same time
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQ(q);
      setOffset(0);
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [q]);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(LIMIT),
        offset: String(offset),
        q: debouncedQ,
      });
      const r = await fetch(`/api/jobs/my?${params}`, { credentials: "include" });
      if (r.status === 401) { router.push("/login"); return; }
      const data = await r.json();
      const loaded: MyJob[] = data.jobs ?? [];
      setJobs(loaded);
      setTotal(data.total ?? 0);
      if (data.storage) setStorage(data.storage);

      // Fetch detail for completed jobs
      const results = await Promise.all(
        loaded
          .filter((j) => j.status === "success")
          .map((j) =>
            fetch(`/api/jobs/${j.job_uuid}`, { credentials: "include" })
              .then((r) => r.json())
              .then((d) => ({ uuid: j.job_uuid, detail: { result: d.result, meta: d.meta, download_url: d.download_url } }))
              .catch(() => null)
          )
      );
      const map: Record<string, JobDetail> = {};
      for (const r of results) {
        if (r) map[r.uuid] = r.detail;
      }
      setDetails(map);
    } finally {
      setLoading(false);
    }
  }, [offset, debouncedQ, router]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const handleCancel = async (job: MyJob) => {
    setCancelling(job.job_uuid);
    try {
      await fetch(`/api/jobs/${job.job_uuid}`, { method: "DELETE", credentials: "include" });
      setJobs((prev) => prev.filter((j) => j.job_uuid !== job.job_uuid));
      setTotal((prev) => Math.max(0, prev - 1));
    } finally {
      setCancelling(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / LIMIT));
  const currentPage = Math.floor(offset / LIMIT) + 1;
  const pageNumbers = (() => {
    const half = 3;
    let start = Math.max(1, currentPage - half);
    const end = Math.min(totalPages, start + 6);
    start = Math.max(1, end - 6);
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  })();

  return (
    <>
      <Header showLogout />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <h2 className="text-lg font-semibold text-gray-800 mb-1">Meine Jobs (letzte 12 Stunden)</h2>
        <p className="text-sm text-gray-500 mb-3">
          Fertige Downloads sind 12 Stunden verfügbar. Ältere Dateien werden automatisch entfernt.
        </p>

        {storage && (
          <div className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
            <span className="font-medium text-gray-600">Gespeichert:</span>
            <span className={storage.video.count >= storage.video.limit ? "text-orange-600 font-medium" : ""}>
              Screencast & Dubbing ({storage.video.count}/{storage.video.limit})
            </span>
            <span className="text-gray-300">·</span>
            <span className={storage.general.count >= storage.general.limit ? "text-orange-600 font-medium" : ""}>
              Andere Tools ({storage.general.count}/{storage.general.limit})
            </span>
          </div>
        )}

        <div className="mb-4">
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Dateiname suchen..."
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : jobs.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-16">
            {debouncedQ ? "Keine Ergebnisse für diese Suche" : "Keine Jobs in den letzten 12 Stunden"}
          </p>
        ) : (
          <>
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

            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-center gap-1">
                <button
                  onClick={() => setOffset(Math.max(0, offset - LIMIT))}
                  disabled={currentPage === 1}
                  className="px-2 py-1 text-sm text-gray-500 hover:text-gray-800 disabled:opacity-30"
                >
                  &lt;
                </button>
                {pageNumbers.map((p) => (
                  <button
                    key={p}
                    onClick={() => setOffset((p - 1) * LIMIT)}
                    className={`px-2.5 py-1 text-sm rounded ${
                      p === currentPage
                        ? "bg-blue-600 text-white font-semibold"
                        : "text-gray-500 hover:text-gray-800"
                    }`}
                  >
                    {p}
                  </button>
                ))}
                <button
                  onClick={() => setOffset(Math.min((totalPages - 1) * LIMIT, offset + LIMIT))}
                  disabled={currentPage === totalPages}
                  className="px-2 py-1 text-sm text-gray-500 hover:text-gray-800 disabled:opacity-30"
                >
                  &gt;
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
