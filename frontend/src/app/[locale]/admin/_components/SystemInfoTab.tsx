"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  Brain,
  Cpu,
  Database,
  Files,
  Funnel,
  Gauge,
  HardDrives,
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
    image_analyze: ModelInfo;
    whisper: ModelInfo;
    tts_active: string[];
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
    <section className="bg-background border border-border-soft rounded-xl p-5">
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

function ModelRow({ label, info, dash }: { label: string; info: ModelInfo; dash: string }) {
  if (!info.provider) {
    return <Row label={label} value={<span className="text-muted">{dash}</span>} />;
  }
  return (
    <div className="py-2 border-b border-border-soft last:border-b-0">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm text-foreground-soft">{label}</p>
        <span className="text-xs font-medium text-kb bg-kb/8 px-2 py-0.5 rounded-full"
              style={{ backgroundColor: "rgba(var(--kb-rgb), 0.08)" }}>
          {info.provider}
        </span>
      </div>
      {info.model && (
        <p className="text-xs font-mono text-muted mt-1 truncate">{info.model}</p>
      )}
    </div>
  );
}

export default function SystemInfoTab() {
  const t = useTranslations("admin");
  const locale = useLocale();
  const numLocale = locale === "en" ? "en-US" : "de-DE";

  const fmtNumber = (n: number): string => n.toLocaleString(numLocale);
  const fmtSeconds = (s: number): string => {
    if (s < 60) return t("systemInfo.secondsUnit", { n: s });
    const m = Math.round(s / 60);
    if (m < 60) return t("systemInfo.minUnit", { n: m });
    const h = m / 60;
    return Number.isInteger(h)
      ? t("systemInfo.hUnit", { n: h })
      : t("systemInfo.hUnitFloat", { n: h.toFixed(1) });
  };

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

  if (error) return <p className="text-sm text-error">{t("loadErrorDetail", { error })}</p>;
  if (!data) return <Spinner className="flex justify-center py-12" />;

  const { models, rate_limits, quotas, uploads, char_limits, workspace_limits, rag, summaries, jobs, celery_timeouts, parallelism, database } = data;

  return (
    <div className="space-y-4">
      <p
        className="text-sm text-muted -mt-2 mb-4"
        dangerouslySetInnerHTML={{ __html: t.raw("systemInfo.intro") as string }}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Section
          icon={<Sparkle size={18} weight="bold" />}
          title={t("systemInfo.modelsTitle")}
          subtitle={t("systemInfo.modelsSubtitle")}
        >
          <ModelRow label={t("systemInfo.modelLlm")} info={models.llm} dash="-" />
          <ModelRow label={t("systemInfo.modelEmbedding")} info={models.embedding} dash="-" />
          <ModelRow label={t("systemInfo.modelOcr")} info={models.ocr} dash="-" />
          <ModelRow label={t("systemInfo.modelImageGen")} info={models.image_gen} dash="-" />
          <ModelRow label={t("systemInfo.modelImageEdit")} info={models.image_edit} dash="-" />
          <ModelRow label={t("systemInfo.modelImageAnalyze")} info={models.image_analyze} dash="-" />
          <ModelRow label={t("systemInfo.modelWhisper")} info={models.whisper} dash="-" />
          <Row
            label={t("systemInfo.ttsActive")}
            value={
              models.tts_active.length === 0 ? (
                <span className="text-muted">-</span>
              ) : (
                <span className="text-xs">{models.tts_active.join(", ")}</span>
              )
            }
          />
        </Section>

        <Section
          icon={<Gauge size={18} weight="bold" />}
          title={t("systemInfo.rateLimitsTitle")}
          subtitle={t("systemInfo.rateLimitsSubtitle")}
        >
          <Row
            label={t("systemInfo.chatBurst")}
            value={`${rate_limits.chat_burst_requests} / ${rate_limits.chat_burst_window_seconds}s`}
          />
          <Row label={t("systemInfo.chatBlock")} value={t("systemInfo.minutesUnit", { n: rate_limits.chat_block_minutes })} />
          <Row
            label={t("systemInfo.toolBurst")}
            value={`${rate_limits.tool_burst_requests} / ${rate_limits.tool_burst_window_seconds}s`}
          />
          <Row label={t("systemInfo.toolBlock")} value={t("systemInfo.minutesUnit", { n: rate_limits.tool_block_minutes })} />
        </Section>

        <Section
          icon={<ListChecks size={18} weight="bold" />}
          title={t("systemInfo.quotasTitle")}
          subtitle={t("systemInfo.quotasSubtitle")}
        >
          {quotas.map((q) => (
            <Row
              key={q.key}
              label={q.label}
              value={`${fmtNumber(q.limit)} / ${q.window_hours}h`}
            />
          ))}
        </Section>

        <Section
          icon={<Files size={18} weight="bold" />}
          title={t("systemInfo.uploadsTitle")}
          subtitle={t("systemInfo.uploadsSubtitle")}
        >
          <Row label={t("systemInfo.uploadGeneral")} value={`${uploads.general_mb} MB`} />
          <Row label={t("systemInfo.uploadTranslate")} value={`${uploads.translate_mb} MB`} />
          <Row label={t("systemInfo.uploadTranscription")} value={`${uploads.transcription_mb} MB`} />
          <Row label={t("systemInfo.uploadImage")} value={`${uploads.image_mb} MB`} />
          <Row label={t("systemInfo.uploadOutputVideo")} value={`${uploads.output_video_mb} MB`} />
        </Section>

        <Section
          icon={<TextAa size={18} weight="bold" />}
          title={t("systemInfo.charLimitsTitle")}
          subtitle={t("systemInfo.charLimitsSubtitle")}
        >
          <Row label={t("systemInfo.charLimitTts")} value={fmtNumber(char_limits.tts)} />
          <Row label={t("systemInfo.charLimitTranslate")} value={fmtNumber(char_limits.translate)} />
          <Row label={t("systemInfo.charLimitSummary")} value={fmtNumber(char_limits.summary)} />
          <Row label={t("systemInfo.charLimitScreencast")} value={fmtNumber(char_limits.screencast)} />
          <Row label={t("systemInfo.charLimitScript")} value={fmtNumber(char_limits.script)} />
        </Section>

        <Section
          icon={<HardDrives size={18} weight="bold" />}
          title={t("systemInfo.workspaceLimitsTitle")}
          subtitle={t("systemInfo.workspaceLimitsSubtitle")}
        >
          <Row label={t("systemInfo.wlSourcesPerWorkspace")} value={fmtNumber(workspace_limits.max_sources_per_workspace)} />
          <Row label={t("systemInfo.wlPagesPerSource")} value={fmtNumber(workspace_limits.max_pages_per_source)} />
          <Row label={t("systemInfo.wlAccessLinks")} value={fmtNumber(workspace_limits.max_access_links)} />
          <Row label={t("systemInfo.wlNotesPerUser")} value={fmtNumber(workspace_limits.max_notes_per_user)} />
          <Row label={t("systemInfo.wlGlossary")} value={fmtNumber(workspace_limits.glossary_limit)} />
          <Row label={t("systemInfo.wlSlidesPerScreencast")} value={fmtNumber(workspace_limits.max_screencast_slides)} />
          <Row label={t("systemInfo.wlQueuedScreencast")} value={fmtNumber(workspace_limits.max_queued_screencast_jobs)} />
        </Section>

        <Section
          icon={<Funnel size={18} weight="bold" />}
          title={t("systemInfo.ragTitle")}
          subtitle={t("systemInfo.ragSubtitle")}
        >
          <Row label={t("systemInfo.ragVectorTopK")} value={fmtNumber(rag.vector_top_k)} hint={t("systemInfo.ragVectorTopKHint")} />
          <Row label={t("systemInfo.ragKeywordTopK")} value={fmtNumber(rag.keyword_top_k)} hint={t("systemInfo.ragKeywordTopKHint")} />
          <Row label={t("systemInfo.ragIlikeFallback")} value={fmtNumber(rag.ilike_fallback_top_k)} hint={t("systemInfo.ragIlikeFallbackHint")} />
          <Row label={t("systemInfo.ragRrfK")} value={fmtNumber(rag.rrf_k)} hint={t("systemInfo.ragRrfKHint")} />
          <Row label={t("systemInfo.ragFinalChunks")} value={fmtNumber(rag.final_chunks_used)} hint={t("systemInfo.ragFinalChunksHint")} />
          <Row label={t("systemInfo.ragEmbedBatch")} value={fmtNumber(rag.embed_batch_size)} hint={t("systemInfo.ragEmbedBatchHint")} />
        </Section>

        <Section
          icon={<Brain size={18} weight="bold" />}
          title={t("systemInfo.summariesTitle")}
          subtitle={t("systemInfo.summariesSubtitle")}
        >
          <Row label={t("systemInfo.sumMaxRetries")} value={fmtNumber(summaries.max_retries)} />
          <Row label={t("systemInfo.sumTimeoutSmall")} value={fmtSeconds(summaries.timeout_small_seconds)} />
          <Row label={t("systemInfo.sumTimeoutLarge")} value={fmtSeconds(summaries.timeout_large_seconds)} />
          <Row label={t("systemInfo.sumMaxTokensSmall")} value={fmtNumber(summaries.max_tokens_small)} />
          <Row label={t("systemInfo.sumMaxTokensLarge")} value={fmtNumber(summaries.max_tokens_large)} />
          <Row label={t("systemInfo.sumMaxTokensBatch")} value={fmtNumber(summaries.max_tokens_batch)} />
          <Row label={t("systemInfo.sumMaxCharsPerPage")} value={fmtNumber(summaries.content_max_chars_per_page)} />
          <Row label={t("systemInfo.sumParallelSmall")} value={fmtNumber(summaries.parallel_workers_small)} hint={t("systemInfo.sumParallelSmallHint")} />
          <Row label={t("systemInfo.sumParallelLarge")} value={fmtNumber(summaries.parallel_workers_large)} hint={t("systemInfo.sumParallelLargeHint")} />
          <Row label={t("systemInfo.sumBatchSize")} value={fmtNumber(summaries.batch_size_pages)} hint={t("systemInfo.sumBatchSizeHint")} />
        </Section>

        <Section
          icon={<Lightning size={18} weight="bold" />}
          title={t("systemInfo.jobsTitle")}
          subtitle={t("systemInfo.jobsSubtitle")}
        >
          <Row label={t("systemInfo.jobsMaxFiles")} value={fmtNumber(jobs.max_result_files_per_user)} hint={t("systemInfo.jobsMaxFilesHint")} />
          <Row label={t("systemInfo.jobsRetention")} value={t("systemInfo.jobsRetentionValue", { hours: jobs.retention_hours, days: Math.round(jobs.retention_hours / 24) })} />
          <Row label={t("systemInfo.jobsWatchdog")} value={t("systemInfo.minutesUnit", { n: jobs.watchdog_minutes })} hint={t("systemInfo.jobsWatchdogHint")} />
        </Section>

        <Section
          icon={<Timer size={18} weight="bold" />}
          title={t("systemInfo.celeryTitle")}
          subtitle={t("systemInfo.celerySubtitle")}
        >
          <Row label={t("systemInfo.celeryTts")} value={`${fmtSeconds(celery_timeouts.tts_soft_seconds)} / ${fmtSeconds(celery_timeouts.tts_hard_seconds)}`} />
          <Row label={t("systemInfo.celeryScreencast")} value={`${fmtSeconds(celery_timeouts.screencast_soft_seconds)} / ${fmtSeconds(celery_timeouts.screencast_hard_seconds)}`} />
          <Row label={t("systemInfo.celeryScreencastAuto")} value={`${fmtSeconds(celery_timeouts.screencast_auto_soft_seconds)} / ${fmtSeconds(celery_timeouts.screencast_auto_hard_seconds)}`} />
        </Section>

        <Section
          icon={<Cpu size={18} weight="bold" />}
          title={t("systemInfo.parallelismTitle")}
          subtitle={t("systemInfo.parallelismSubtitle")}
        >
          <Row label={t("systemInfo.renderWorkers")} value={fmtNumber(parallelism.render_workers)} />
          <Row label={t("systemInfo.cpuCount")} value={fmtNumber(parallelism.cpu_count)} />
          <Row
            label={t("systemInfo.ruleOfThumb")}
            value={<span className="text-xs text-muted">{t("systemInfo.ruleOfThumbValue")}</span>}
            hint={t("systemInfo.ruleOfThumbHint")}
          />
        </Section>

        <Section
          icon={<Database size={18} weight="bold" />}
          title={t("systemInfo.databaseTitle")}
          subtitle={t("systemInfo.databaseSubtitle")}
        >
          <Row label={t("systemInfo.poolMin")} value={fmtNumber(database.pool_min)} />
          <Row label={t("systemInfo.poolMax")} value={fmtNumber(database.pool_max)} />
        </Section>
      </div>

    </div>
  );
}
