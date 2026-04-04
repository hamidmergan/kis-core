"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { checkAuthStatus } from "@/lib/auth";
import Header from "@/components/Header";
import { getToolConfigByJobTool } from "@/lib/toolConfig";
import BackLink from "@/components/BackLink";
import { ArrowsCounterClockwise, DownloadSimple, Trash } from "@phosphor-icons/react";
import IconButton from "@/components/IconButton";

interface MyJob {
  job_uuid: string;
  tool: string;
  tool_label: string;
  original_filename: string;
  status: "pending" | "running" | "success" | "failed" | "awaiting_user" | "queued";
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  render_started_at: string | null;
  render_queued_at: string | null;
  expires_at: string | null;
  has_download: boolean;
  result_filename: string | null;
  folder_name: string | null;
  tts_params?: { voice_id?: string; voice_label?: string; provider?: string } | null;
  is_generating_scripts?: boolean;
  meta?: Record<string, unknown> | null;
}



const SCREENCAST_RENDER_TOOLS = new Set(["screencast_render", "screencast_auto", "screencast_demo_render"]);
const SCREENCAST_TOOLS = new Set(["screencast_translate", "screencast_render", "screencast_auto", "screencast_demo_render"]);
const isActive = (s: MyJob["status"]) => s === "pending" || s === "running" || s === "awaiting_user" || s === "queued";
const isExpired = (job: MyJob) => job.status === "success" && !job.has_download;

function StatusBadge({ status, expired, isGeneratingScripts }: { status: MyJob["status"]; expired: boolean; isGeneratingScripts?: boolean }) {
  if (expired)
    return <span className="inline-flex text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">Abgelaufen</span>;
  if (status === "success")
    return <span className="inline-flex text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">Fertig</span>;
  if (status === "failed")
    return <span className="inline-flex text-xs font-medium text-red-700 bg-red-100 px-2 py-0.5 rounded-full">Fehler</span>;
  if (status === "running" || isGeneratingScripts)
    return <span className="inline-flex text-xs font-medium text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full animate-pulse">Läuft</span>;
  if (status === "awaiting_user")
    return <span className="inline-flex text-xs font-medium text-orange-700 bg-orange-100 px-2 py-0.5 rounded-full">Eingabe erforderlich</span>;
  if (status === "queued")
    return <span className="inline-flex text-xs font-medium text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full">In der Schlange</span>;
  return <span className="inline-flex text-xs font-medium text-yellow-700 bg-yellow-100 px-2 py-0.5 rounded-full">Wartend</span>;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin",
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
  return new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").getTime();
}

function TimingInfo({ job, isAdmin }: { job: MyJob; isAdmin: boolean }) {
  if (SCREENCAST_TOOLS.has(job.tool)) {
    const queueWaitMs = job.render_queued_at && job.render_started_at
      ? toMs(job.render_started_at) - toMs(job.render_queued_at)
      : null;
    const renderMs = job.render_started_at && job.completed_at
      ? toMs(job.completed_at) - toMs(job.render_started_at)
      : null;
    return (
      <div className="mt-1.5 text-xs text-gray-400 space-y-0.5">
        <p>Eingereicht: {formatDate(job.created_at)}</p>
        {isAdmin && queueWaitMs !== null && (
          <p>Wartezeit: <span className="text-gray-500">{formatDuration(queueWaitMs)}</span></p>
        )}
        {isAdmin && renderMs !== null && (
          <p>Renderzeit: <span className="text-gray-500">{formatDuration(renderMs)}</span></p>
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

  const waitMs = job.started_at ? toMs(job.started_at) - toMs(job.created_at) : null;
  const workMs = job.started_at && job.completed_at ? toMs(job.completed_at) - toMs(job.started_at) : null;
  return (
    <div className="mt-1.5 text-xs text-gray-400 space-y-0.5">
      <p>Eingereicht: {formatDate(job.created_at)}</p>
      {isAdmin && waitMs !== null && (
        <p>Wartezeit: <span className="text-gray-500">{formatDuration(waitMs)}</span></p>
      )}
      {isAdmin && workMs !== null && (
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



function downloadText(text: string, filename: string, mimeType: string) {
  const blob = new Blob([text], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function DownloadChip({ onClick, href, filename, label }: { onClick?: () => void | Promise<void>; href?: string; filename?: string; label: string }) {
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
      className="text-xs text-primary hover:underline flex items-center gap-1 disabled:opacity-60 disabled:cursor-not-allowed"
    >
      {busy ? (
        <span className="w-3 h-3 shrink-0 border-2 border-primary border-t-transparent rounded-full animate-spin inline-block" aria-hidden="true" />
      ) : (
        <DownloadSimple size={12} weight="bold" className="shrink-0" />
      )}
      {busy ? "Wird erstellt…" : label}
    </button>
  );
}

// Legacy alias for single-href usage
function DownloadButton({ href, filename, label }: { href?: string; filename?: string; label: string }) {
  return <DownloadChip href={href} filename={filename} label={label} />;
}

function DisabledChip({ label }: { label: string }) {
  return (
    <span className="text-xs text-gray-400 flex items-center gap-1 cursor-not-allowed select-none">
      <DownloadSimple size={12} weight="bold" className="shrink-0" />
      {label}
    </span>
  );
}

function JobArtifacts({ job }: { job: MyJob }) {
  // screencast_translate: single-folder workflow — show artifacts for both phases
  if (job.tool === "screencast_translate") {
    if (job.status === "awaiting_user") {
      return (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap gap-2 items-center">
            <DisabledChip label="MP4" />
            <DisabledChip label="Alles herunterladen (ZIP)" />
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            {job.is_generating_scripts ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-gray-500 bg-gray-50 border border-gray-200 px-2.5 py-1 rounded-full">
                <span className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin inline-block shrink-0" />
                Skripte werden generiert…
              </span>
            ) : (
              <a
                href={`/screencast?resume=${job.job_uuid}`}
                className="inline-flex items-center gap-1 text-xs text-orange-700 bg-orange-50 hover:bg-orange-100 border border-orange-200 px-2.5 py-1 rounded-full"
              >
                Screencast fortsetzen →
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
                label="Alles herunterladen (ZIP)"
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
          <DisabledChip label="Alles herunterladen (ZIP)" />
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          {job.is_generating_scripts ? (
            <span className="inline-flex items-center gap-1.5 text-xs text-gray-500 bg-gray-50 border border-gray-200 px-2.5 py-1 rounded-full">
              <span className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin inline-block shrink-0" />
              Skripte werden generiert…
            </span>
          ) : (
            <a
              href={`/screencast-demo?resume=${job.job_uuid}`}
              className="inline-flex items-center gap-1 text-xs text-orange-700 bg-orange-50 hover:bg-orange-100 border border-orange-200 px-2.5 py-1 rounded-full"
            >
              Demo fortsetzen →
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
              label="Alles herunterladen (ZIP)"
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
        <DownloadButton
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
      job.tool === "image_generate"
        ? job.result_filename?.endsWith(".json")
          ? "ZIP"
          : "PNG"
        : job.tool === "image_edit"
        ? "PNG"
        : job.tool === "image_analyze"
        ? "TXT"
        : (job.tool === "transcription" || job.tool === "translation" || job.tool === "summary")
        ? (job.result_filename?.split(".").pop()?.toUpperCase() ?? "Datei")
        : "Datei";
    const downloadFilename =
      job.tool === "image_generate" && job.result_filename?.endsWith(".json")
        ? job.result_filename.replace(".json", ".zip")
        : job.result_filename || "download";
    return (
      <div className="mt-3">
        <DownloadButton
          href={`/api/jobs/${job.job_uuid}/download`}
          filename={downloadFilename}
          label={downloadLabel}
        />
      </div>
    );
  }

  return null;
}


export default function MeineJobsPage() {
  const [jobs, setJobs] = useState<MyJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const ss = (key: string, fallback: string) => typeof window !== "undefined" ? (sessionStorage.getItem(key) ?? fallback) : fallback;
  const [q, setQ] = useState(() => ss("mj_q", ""));
  const [debouncedQ, setDebouncedQ] = useState(() => ss("mj_q", ""));
  const [toolFilter, setToolFilter] = useState(() => ss("mj_tool", ""));
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(() => Number(ss("mj_limit", "10")));
  const [dateFrom, setDateFrom] = useState(() => ss("mj_from", ""));
  const [dateTo, setDateTo] = useState(() => ss("mj_to", ""));
  const [isAdmin, setIsAdmin] = useState(false);
  const [enabledTools, setEnabledTools] = useState<Set<string>>(new Set());
  const [deleteConfirm, setDeleteConfirm] = useState<MyJob | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const router = useRouter();

  useEffect(() => {
    checkAuthStatus().then((s) => setIsAdmin(s.is_admin ?? false));
    fetch("/api/admin/tools", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setEnabledTools(new Set((d.tools ?? []).filter((t: { enabled: boolean }) => t.enabled).map((t: { key: string }) => t.key))))
      .catch(() => {});
  }, []);

  // Debounce q and reset offset
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQ(q);
      setOffset(0);
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [q]);

  // Persist filters to sessionStorage
  useEffect(() => { sessionStorage.setItem("mj_q", q); }, [q]);
  useEffect(() => { sessionStorage.setItem("mj_tool", toolFilter); }, [toolFilter]);
  useEffect(() => { sessionStorage.setItem("mj_limit", String(limit)); }, [limit]);
  useEffect(() => { sessionStorage.setItem("mj_from", dateFrom); }, [dateFrom]);
  useEffect(() => { sessionStorage.setItem("mj_to", dateTo); }, [dateTo]);

  const resetFilters = () => {
    setQ(""); setToolFilter(""); setDateFrom(""); setDateTo(""); setLimit(10); setOffset(0);
  };
  const hasActiveFilters = q || toolFilter || dateFrom || dateTo;

  // Reset offset when limit, dates or tool filter change
  useEffect(() => { setOffset(0); }, [limit, dateFrom, dateTo, toolFilter]);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
        q: debouncedQ,
      });
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      if (toolFilter) params.set("tool_filter", toolFilter);
      const r = await fetch(`/api/jobs/my?${params}`, { credentials: "include" });
      if (r.status === 401) { router.push("/login"); return; }
      const data = await r.json();
      const loaded: MyJob[] = data.jobs ?? [];
      setJobs(loaded);
      setTotal(data.total ?? 0);
      setLastUpdated(new Date());
    } finally {
      setLoading(false);
    }
  }, [offset, debouncedQ, toolFilter, limit, dateFrom, dateTo, router]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Refresh when JobsPanel detects a status change (e.g. running→success)
  useEffect(() => {
    const handler = () => fetchJobs();
    window.addEventListener("kis-jobs-status-changed", handler);
    return () => window.removeEventListener("kis-jobs-status-changed", handler);
  }, [fetchJobs]);

  const handleRetry = async (job: MyJob) => {
    setRetrying(job.job_uuid);
    try {
      const res = await fetch(`/api/jobs/${job.job_uuid}/retry`, { method: "POST", credentials: "include" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Wiederholen fehlgeschlagen");
        return;
      }
      await fetchJobs();
    } finally {
      setRetrying(null);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm) return;
    setDeleting(deleteConfirm.job_uuid);
    try {
      await fetch(`/api/jobs/${deleteConfirm.job_uuid}`, { method: "DELETE", credentials: "include" });
      setJobs((prev) => prev.filter((j) => j.job_uuid !== deleteConfirm.job_uuid));
      setTotal((prev) => Math.max(0, prev - 1));
      setDeleteConfirm(null);
    } finally {
      setDeleting(null);
    }
  };

  const handleCancel = async (job: MyJob) => {
    setCancelling(job.job_uuid);
    try {
      await fetch(`/api/jobs/${job.job_uuid}`, { method: "DELETE", credentials: "include" });
      setJobs((prev) => prev.filter((j) => j.job_uuid !== job.job_uuid));
      setTotal((prev) => Math.max(0, prev - 1));
      window.dispatchEvent(new Event("kis-jobs-changed"));
    } finally {
      setCancelling(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;
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
      <main className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Meine Jobs</h2>
          <div className="flex items-center gap-2">
            {lastUpdated && !loading && (
              <span className="text-xs text-gray-400">
                {lastUpdated.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" })}
              </span>
            )}
            <button
              onClick={() => { fetchJobs(); window.dispatchEvent(new CustomEvent("kis-jobs-changed")); }}
              disabled={loading}
              title="Aktualisieren"
              className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 disabled:opacity-40 transition-colors"
            >
              <ArrowsCounterClockwise size={16} className={loading ? "animate-spin" : ""} />
              Aktualisieren
            </button>
          </div>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Es werden bis zu 20 Jobs gespeichert. Fertige Downloads sind 7 Tage verfügbar. Ältere Dateien werden automatisch entfernt.
        </p>

        {/* Search/filter bar */}
        <div className="mb-4 flex flex-wrap gap-2 items-center">
          <div className="flex-1 min-w-[220px] flex items-center border border-gray-300 rounded-md bg-white focus-within:ring-2 focus-within:ring-primary">
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Suche"
              className="flex-1 text-sm px-3 py-2 bg-transparent outline-none min-w-0"
            />
            <div className="w-px h-5 bg-gray-200 shrink-0" />
            <select
              value={toolFilter}
              onChange={(e) => setToolFilter(e.target.value)}
              className="text-sm px-2 py-2 bg-transparent outline-none text-gray-500 cursor-pointer appearance-none pr-3"
            >
              <option value="">Alle Tools</option>
              <option value="transcription">Speech-to-Text</option>
              <option value="translation">Translate</option>
              <option value="summary">Summarize</option>
              <option value="tts">Text-to-Speech</option>
              <option value="screencast">Screencast</option>
              <option value="image">Image</option>
            </select>
          </div>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            title="Von"
            className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            title="Bis"
            className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="hidden"
          >
            <option value={10}>10 pro Seite</option>
            <option value={25}>25 pro Seite</option>
            <option value={50}>50 pro Seite</option>
          </select>
          <span className="text-xs text-gray-400 whitespace-nowrap">
            {total} Ergebnis{total !== 1 ? "se" : ""}
          </span>
          {hasActiveFilters && (
            <button
              onClick={resetFilters}
              className="text-xs text-gray-400 hover:text-gray-700 underline whitespace-nowrap"
            >
              Filter zurücksetzen
            </button>
          )}
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : jobs.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-16">
            {debouncedQ ? "Keine Ergebnisse für diese Suche" : "Keine Jobs in den letzten 7 Tagen"}
          </p>
        ) : (
          <>
            <ul className="divide-y divide-gray-200 rounded-xl overflow-hidden" style={{ backgroundColor: "var(--surface)" }}>
              {jobs.map((job) => {
                const expired = isExpired(job);
                return (
                  <li key={job.job_uuid} className={`px-5 py-4 ${expired ? "opacity-50" : ""}`}>
                    <div className="flex items-stretch justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <span
                            className="w-2 h-2 rounded-full flex-shrink-0"
                            style={{ backgroundColor: getToolConfigByJobTool(job.tool).color }}
                          />
                          <p className="text-sm font-medium text-gray-800">{job.tool_label}</p>
                        </div>
                        <p className="text-xs text-gray-400 truncate mt-0.5">{job.original_filename}</p>
                        {job.tts_params?.voice_label || job.tts_params?.provider ? (
                          <p className="text-xs text-gray-400 mt-0.5">
                            {job.tts_params.provider === "kokoro" ? "Kokoro TTS" : job.tts_params.provider === "mylab" ? "THL myLab" : job.tts_params.provider === "thorsten" ? "Thorsten" : job.tts_params.provider === "elevenlabs" ? "ElevenLabs" : job.tts_params.provider}
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
                            onClick={() => handleCancel(job)}
                            disabled={cancelling === job.job_uuid}
                            className="text-xs text-red-500 hover:underline disabled:opacity-50"
                          >
                            {cancelling === job.job_uuid ? "..." : "Abbrechen"}
                          </button>
                        )}
                        {(job.tool === "tts" || job.tool === "screencast_translate" || job.tool === "screencast_render" || job.tool === "screencast_demo_render") && job.status === "failed" && (
                          <button
                            onClick={() => handleRetry(job)}
                            disabled={retrying === job.job_uuid}
                            className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                          >
                            {retrying === job.job_uuid ? "..." : "Wiederholen"}
                          </button>
                        )}
                        {!isActive(job.status) && (
                          <IconButton
                            onClick={() => setDeleteConfirm(job)}
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
              })}
            </ul>

            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-center gap-1 pt-2">
                <button
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  disabled={currentPage === 1}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-40 hover:bg-gray-50"
                >
                  ‹
                </button>
                {pageNumbers.map((p) => (
                  <button
                    key={p}
                    onClick={() => setOffset((p - 1) * limit)}
                    className={`px-3 py-1.5 text-sm border rounded-md ${
                      p === currentPage
                        ? "bg-primary text-white border-primary"
                        : "border-gray-300 hover:bg-gray-50"
                    }`}
                  >
                    {p}
                  </button>
                ))}
                <button
                  onClick={() => setOffset(Math.min((totalPages - 1) * limit, offset + limit))}
                  disabled={currentPage === totalPages}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-40 hover:bg-gray-50"
                >
                  ›
                </button>
              </div>
            )}
          </>
        )}
      </main>

      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold text-gray-900 mb-2">Job löschen?</h3>
            <p className="text-sm text-gray-600 mb-1">
              <span className="font-medium">{deleteConfirm.tool_label}</span> – {deleteConfirm.original_filename}
            </p>
            <p className="text-sm text-red-600 mb-6">
              Der Job wird vollständig entfernt und ist nicht mehr herunterladbar.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteConfirm(null)}
                disabled={!!deleting}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                Abbrechen
              </button>
              <button
                onClick={handleDeleteConfirm}
                disabled={!!deleting}
                className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50"
              >
                {deleting ? "..." : "Löschen"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
