"use client";

import { useEffect, useState } from "react";
import {
  Brain,
  Cpu,
  Database,
  Files,
  Funnel,
  Gauge,
  HardDrives,
  Hourglass,
  Lightning,
  ListChecks,
  Sparkle,
  TextAa,
  Timer,
} from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";

interface ModelInfo {
  provider: string | null;
  model: string | null;
}

interface QuotaEntry {
  key: string;
  label: string;
  limit: number;
  window_hours: number;
}

interface SystemInfo {
  models: {
    llm: ModelInfo;
    embedding: ModelInfo;
    ocr: ModelInfo;
    image_gen: ModelInfo;
    image_edit: ModelInfo;
    whisper: ModelInfo;
    tts_active: string[];
    tts_mylab_model: string | null;
  };
  rate_limits: Record<string, number>;
  quotas: QuotaEntry[];
  uploads: Record<string, number>;
  char_limits: Record<string, number>;
  workspace_limits: Record<string, number>;
  rag: Record<string, number>;
  summaries: Record<string, number>;
  jobs: Record<string, number>;
  celery_timeouts: Record<string, number>;
  parallelism: Record<string, number>;
  database: Record<string, number>;
}

const PROVIDER_LABEL: Record<string, string> = {
  kisski: "KISSKI",
  mylab: "myLab",
  ollama: "Ollama (lokal)",
};

function fmtSeconds(s: number): string {
  if (s < 60) return `${s} s`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min`;
  const h = m / 60;
  return Number.isInteger(h) ? `${h} h` : `${h.toFixed(1)} h`;
}

function fmtNumber(n: number): string {
  return n.toLocaleString("de-DE");
}

function Section({
  icon,
  title,
  subtitle,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-white border border-border-soft rounded-xl p-5">
      <div className="flex items-start gap-3 mb-4">
        <span className="mt-0.5 w-8 h-8 rounded-lg bg-kb/8 text-kb flex items-center justify-center shrink-0"
              style={{ backgroundColor: "rgba(var(--kb-rgb), 0.08)" }}>
          {icon}
        </span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          {subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

function Row({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-2 border-b border-border-soft last:border-b-0">
      <div className="min-w-0">
        <p className="text-sm text-foreground-soft">{label}</p>
        {hint && <p className="text-[11px] text-muted-soft mt-0.5">{hint}</p>}
      </div>
      <p className="text-sm font-mono font-medium text-foreground tabular-nums whitespace-nowrap">{value}</p>
    </div>
  );
}

function ModelRow({ label, info }: { label: string; info: ModelInfo }) {
  if (!info.provider) {
    return <Row label={label} value={<span className="text-muted">-</span>} />;
  }
  const provider = PROVIDER_LABEL[info.provider] ?? info.provider;
  return (
    <div className="py-2 border-b border-border-soft last:border-b-0">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm text-foreground-soft">{label}</p>
        <span className="text-xs font-medium text-kb bg-kb/8 px-2 py-0.5 rounded-full"
              style={{ backgroundColor: "rgba(var(--kb-rgb), 0.08)" }}>
          {provider}
        </span>
      </div>
      {info.model && (
        <p className="text-xs font-mono text-muted mt-1 truncate">{info.model}</p>
      )}
    </div>
  );
}

export default function SystemInfoTab() {
  const [data, setData] = useState<SystemInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/system-info", { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="text-sm text-error">Fehler beim Laden: {error}</p>;
  if (!data) return <Spinner className="flex justify-center py-12" />;

  const { models, rate_limits, quotas, uploads, char_limits, workspace_limits, rag, summaries, jobs, celery_timeouts, parallelism, database } = data;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted -mt-2 mb-4">
        Übersicht der aktuell konfigurierten Werte. Nur lesbar - Änderungen erfolgen im Code (
        <code className="text-[11px] bg-surface-dim px-1.5 py-0.5 rounded">backend/src/limits.py</code>
        ) bzw. unter „KI" und „System".
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* ── Active models ───────────────────────────────────────── */}
        <Section
          icon={<Sparkle size={18} weight="bold" />}
          title="Aktive Modelle"
          subtitle="Pro Fähigkeit ein Provider. Auswahl unter KI."
        >
          <ModelRow label="LLM (Chat)" info={models.llm} />
          <ModelRow label="Embedding" info={models.embedding} />
          <ModelRow label="OCR" info={models.ocr} />
          <ModelRow label="Bild-Generierung" info={models.image_gen} />
          <ModelRow label="Bild-Bearbeitung" info={models.image_edit} />
          <ModelRow label="Transkription (Whisper)" info={models.whisper} />
          <Row
            label="TTS-Provider aktiv"
            value={
              models.tts_active.length === 0 ? (
                <span className="text-muted">-</span>
              ) : (
                <span className="text-xs">{models.tts_active.join(", ")}</span>
              )
            }
          />
          {models.tts_mylab_model && (
            <Row label="myLab TTS Modell" value={<span className="text-xs">{models.tts_mylab_model}</span>} />
          )}
        </Section>

        {/* ── Rate limits ─────────────────────────────────────────── */}
        <Section
          icon={<Gauge size={18} weight="bold" />}
          title="Rate-Limits (Burst-Schutz)"
          subtitle="Greift bei Bots/Bugs. Keine Tages-/Stunden-Limits."
        >
          <Row
            label="Chat: max Anfragen / Fenster"
            value={`${rate_limits.chat_burst_requests} / ${rate_limits.chat_burst_window_seconds}s`}
          />
          <Row label="Chat: Sperrdauer bei Auslösen" value={`${rate_limits.chat_block_minutes} min`} />
          <Row
            label="Tools: max Anfragen / Fenster"
            value={`${rate_limits.tool_burst_requests} / ${rate_limits.tool_burst_window_seconds}s`}
          />
          <Row label="Tools: Sperrdauer bei Auslösen" value={`${rate_limits.tool_block_minutes} min`} />
        </Section>

        {/* ── Quotas ──────────────────────────────────────────────── */}
        <Section
          icon={<ListChecks size={18} weight="bold" />}
          title="Standard-Quotas pro Nutzer"
          subtitle={"Pro-Nutzer-Overrides unter „Alle User“ → Quota."}
        >
          {quotas.map((q) => (
            <Row
              key={q.key}
              label={q.label}
              value={`${fmtNumber(q.limit)} / ${q.window_hours}h`}
            />
          ))}
        </Section>

        {/* ── Upload sizes ───────────────────────────────────────── */}
        <Section
          icon={<Files size={18} weight="bold" />}
          title="Upload-Größen"
          subtitle="Maximalgröße pro hochgeladener Datei."
        >
          <Row label="Allgemein" value={`${uploads.general_mb} MB`} />
          <Row label="Übersetzung" value={`${uploads.translate_mb} MB`} />
          <Row label="Audio (Transkription)" value={`${uploads.transcription_mb} MB`} />
          <Row label="Bild" value={`${uploads.image_mb} MB`} />
          <Row label="Video-Output (Screencast)" value={`${uploads.output_video_mb} MB`} />
        </Section>

        {/* ── Char limits ────────────────────────────────────────── */}
        <Section
          icon={<TextAa size={18} weight="bold" />}
          title="Zeichenlimits pro Anfrage"
          subtitle="Max. Eingabelänge pro Tool-Request."
        >
          <Row label="TTS" value={fmtNumber(char_limits.tts)} />
          <Row label="Übersetzung" value={fmtNumber(char_limits.translate)} />
          <Row label="Zusammenfassung" value={fmtNumber(char_limits.summary)} />
          <Row label="Screencast" value={fmtNumber(char_limits.screencast)} />
          <Row label="Skript" value={fmtNumber(char_limits.script)} />
        </Section>

        {/* ── Workspace limits ───────────────────────────────────── */}
        <Section
          icon={<HardDrives size={18} weight="bold" />}
          title="Workspace- & Inhalts-Limits"
          subtitle="Begrenzung pro Workspace bzw. Nutzer."
        >
          <Row label="Quellen pro Workspace" value={fmtNumber(workspace_limits.max_sources_per_workspace)} />
          <Row label="Seiten pro Quelle (PDF/PPTX/DOCX)" value={fmtNumber(workspace_limits.max_pages_per_source)} />
          <Row label="Zugangslinks pro Workspace" value={fmtNumber(workspace_limits.max_access_links)} />
          <Row label="Notizen pro Nutzer" value={fmtNumber(workspace_limits.max_notes_per_user)} />
          <Row label="Glossar-Einträge" value={fmtNumber(workspace_limits.glossary_limit)} />
          <Row label="Folien pro Screencast" value={fmtNumber(workspace_limits.max_screencast_slides)} />
          <Row label="Screencast-Jobs in Warteschlange" value={fmtNumber(workspace_limits.max_queued_screencast_jobs)} />
        </Section>

        {/* ── RAG retrieval ──────────────────────────────────────── */}
        <Section
          icon={<Funnel size={18} weight="bold" />}
          title="RAG-Retrieval (KI-Tutor)"
          subtitle="Hybrid-Suche aus Vektor + Keyword (BM25) via RRF-Fusion."
        >
          <Row label="Vector-Suche Top-K" value={fmtNumber(rag.vector_top_k)} hint="Kandidaten aus pgvector" />
          <Row label="Keyword-Suche Top-K" value={fmtNumber(rag.keyword_top_k)} hint="ts_rank_cd, OR-Verknüpfung" />
          <Row label="ILIKE-Fallback Top-K" value={fmtNumber(rag.ilike_fallback_top_k)} hint="Eigennamen / Nicht-Deutsch" />
          <Row label="RRF-Konstante k" value={fmtNumber(rag.rrf_k)} hint="Reciprocal Rank Fusion" />
          <Row label="Final genutzte Chunks" value={fmtNumber(rag.final_chunks_used)} hint="Werden ans LLM gegeben" />
          <Row label="Embedding Batch-Größe" value={fmtNumber(rag.embed_batch_size)} hint="Beim Indexieren" />
        </Section>

        {/* ── Page summaries ─────────────────────────────────────── */}
        <Section
          icon={<Brain size={18} weight="bold" />}
          title="Seiten-Zusammenfassungen (Pipeline)"
          subtitle="Werden beim Hochladen einer Quelle erstellt."
        >
          <Row label="Max Retries" value={fmtNumber(summaries.max_retries)} />
          <Row label="Timeout pro Seite (Ollama)" value={fmtSeconds(summaries.timeout_small_seconds)} />
          <Row label="Timeout pro Seite (Cloud)" value={fmtSeconds(summaries.timeout_large_seconds)} />
          <Row label="Max Tokens (Ollama, einzeln)" value={fmtNumber(summaries.max_tokens_small)} />
          <Row label="Max Tokens (Cloud, einzeln)" value={fmtNumber(summaries.max_tokens_large)} />
          <Row label="Max Tokens (Cloud, Batch)" value={fmtNumber(summaries.max_tokens_batch)} />
          <Row label="Max Zeichen pro Seite an LLM" value={fmtNumber(summaries.content_max_chars_per_page)} />
          <Row label="Parallele Worker (Ollama)" value={fmtNumber(summaries.parallel_workers_small)} hint="Mehrere Seiten parallel" />
          <Row label="Parallele Worker (Cloud)" value={fmtNumber(summaries.parallel_workers_large)} hint="Sequenziell für Stabilität" />
          <Row label="Seiten pro Batch" value={fmtNumber(summaries.batch_size_pages)} hint="Cloud, mehrere Seiten in einer Anfrage" />
        </Section>

        {/* ── Jobs ───────────────────────────────────────────────── */}
        <Section
          icon={<Lightning size={18} weight="bold" />}
          title="Job-Verwaltung"
          subtitle="Ergebnisdateien & Watchdog für Tool-Jobs."
        >
          <Row label="Max Ergebnis-Dateien pro Nutzer" value={fmtNumber(jobs.max_result_files_per_user)} hint="Älteste werden überschrieben" />
          <Row label="Aufbewahrung Ergebnisse" value={`${jobs.retention_hours} h (${Math.round(jobs.retention_hours / 24)} Tage)`} />
          <Row label="Watchdog ohne Heartbeat" value={`${jobs.watchdog_minutes} min`} hint="Danach gilt Job als hängend" />
        </Section>

        {/* ── Celery timeouts ────────────────────────────────────── */}
        <Section
          icon={<Timer size={18} weight="bold" />}
          title="Task-Timeouts (Celery)"
          subtitle="Soft-Limit = sauberes Abbrechen, Hard-Limit = SIGKILL."
        >
          <Row label="TTS (soft / hard)" value={`${fmtSeconds(celery_timeouts.tts_soft_seconds)} / ${fmtSeconds(celery_timeouts.tts_hard_seconds)}`} />
          <Row label="Screencast (soft / hard)" value={`${fmtSeconds(celery_timeouts.screencast_soft_seconds)} / ${fmtSeconds(celery_timeouts.screencast_hard_seconds)}`} />
          <Row label="Screencast Auto-Pipeline" value={`${fmtSeconds(celery_timeouts.screencast_auto_soft_seconds)} / ${fmtSeconds(celery_timeouts.screencast_auto_hard_seconds)}`} />
        </Section>

        {/* ── Parallelism ────────────────────────────────────────── */}
        <Section
          icon={<Cpu size={18} weight="bold" />}
          title="Parallelisierung & CPU"
          subtitle="ThreadPool-Größen für Render-Tasks."
        >
          <Row label="Render-Worker (PDF→PNG, FFmpeg)" value={fmtNumber(parallelism.render_workers)} />
          <Row label="CPU-Kerne im Container" value={fmtNumber(parallelism.cpu_count)} />
          <Row
            label="Daumenregel"
            value={<span className="text-xs text-muted">Worker ≈ Kerne / 2</span>}
            hint="Reserve für Uvicorn + OS"
          />
        </Section>

        {/* ── Database ───────────────────────────────────────────── */}
        <Section
          icon={<Database size={18} weight="bold" />}
          title="Datenbank-Pool"
          subtitle="Postgres-Connection-Pool (psycopg2 ThreadedPool)."
        >
          <Row label="Pool min" value={fmtNumber(database.pool_min)} />
          <Row label="Pool max" value={fmtNumber(database.pool_max)} />
        </Section>
      </div>

    </div>
  );
}
