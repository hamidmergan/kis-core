import { useLocale, useTranslations } from "next-intl";
import { SCREENCAST_TOOLS, type MyJob } from "../_types";
import { formatDate, formatElapsed, toMs } from "@/lib/format";


export function TimingInfo({ job, isAdmin }: { job: MyJob; isAdmin: boolean }) {
  const locale = useLocale();
  const t = useTranslations("myJobs.timing");
  const td = useTranslations("myJobs.duration");
  const fmt = {
    seconds: (n: number) => td("seconds", { n }),
    minutes: (m: number, s: string) => td("minutes", { m, s }),
    hours: (h: number, m: string, s: string) => td("hours", { h, m, s }),
  };

  if (SCREENCAST_TOOLS.has(job.tool)) {
    const queueWaitMs = job.render_queued_at && job.render_started_at
      ? toMs(job.render_started_at) - toMs(job.render_queued_at)
      : null;
    const renderMs = job.render_started_at && job.completed_at
      ? toMs(job.completed_at) - toMs(job.render_started_at)
      : null;
    return (
      <div className="mt-1.5 text-xs text-muted-soft space-y-0.5">
        <p>{t("submitted")} {formatDate(job.created_at, locale)}</p>
        {isAdmin && queueWaitMs !== null && (
          <p>{t("queueWait")} <span className="text-muted">{formatElapsed(queueWaitMs, fmt)}</span></p>
        )}
        {isAdmin && renderMs !== null && (
          <p>{t("renderTime")} <span className="text-muted">{formatElapsed(renderMs, fmt)}</span></p>
        )}
        {job.completed_at && (
          <p>{t("completed")} {formatDate(job.completed_at, locale)}</p>
        )}
        {job.expires_at && (
          <p>{t("expiresAt")} {formatDate(job.expires_at, locale)}</p>
        )}
      </div>
    );
  }

  const waitMs = job.started_at ? toMs(job.started_at) - toMs(job.created_at) : null;
  const workMs = job.started_at && job.completed_at ? toMs(job.completed_at) - toMs(job.started_at) : null;
  return (
    <div className="mt-1.5 text-xs text-muted-soft space-y-0.5">
      <p>{t("submitted")} {formatDate(job.created_at, locale)}</p>
      {isAdmin && waitMs !== null && (
        <p>{t("queueWait")} <span className="text-muted">{formatElapsed(waitMs, fmt)}</span></p>
      )}
      {isAdmin && workMs !== null && (
        <p>{t("processingTime")} <span className="text-muted">{formatElapsed(workMs, fmt)}</span></p>
      )}
      {job.completed_at && (
        <p>{t("completed")} {formatDate(job.completed_at, locale)}</p>
      )}
      {job.expires_at && (
        <p>{t("expiresAt")} {formatDate(job.expires_at, locale)}</p>
      )}
    </div>
  );
}
