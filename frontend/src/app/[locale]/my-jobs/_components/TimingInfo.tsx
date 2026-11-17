import { useLocale, useTranslations } from "next-intl";
import { isScreencast } from "@/components/jobs/_myJob";
import type { MyJob } from "../_types";
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

  // A screencast counts from the render queue, every other job from its own start.
  const screencast = isScreencast(job);
  const [queuedAt, startedAt] = screencast ? [job.render_queued_at, job.render_started_at] : [job.created_at, job.started_at];
  const waitMs = queuedAt && startedAt ? toMs(startedAt) - toMs(queuedAt) : null;
  const workMs = startedAt && job.completed_at ? toMs(job.completed_at) - toMs(startedAt) : null;
  return (
    <div className="mt-1.5 text-xs text-muted-soft space-y-0.5">
      <p>{t("submitted")} {formatDate(job.created_at, locale)}</p>
      {isAdmin && waitMs !== null && (
        <p>{t("queueWait")} <span className="text-muted">{formatElapsed(waitMs, fmt)}</span></p>
      )}
      {isAdmin && workMs !== null && (
        <p>{t(screencast ? "renderTime" : "processingTime")} <span className="text-muted">{formatElapsed(workMs, fmt)}</span></p>
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
