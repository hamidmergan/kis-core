import { useTranslations } from "next-intl";
import type { MyJob } from "../_types";


interface StatusBadgeProps {
  status: MyJob["status"];
  expired: boolean;
  isGeneratingScripts?: boolean;
  resumeHref?: string;
  onResume?: () => void;
}


export function StatusBadge({ status, expired, isGeneratingScripts, resumeHref, onResume }: StatusBadgeProps) {
  const t = useTranslations("myJobs.status");
  if (expired)
    return <span className="inline-flex text-xs font-medium text-muted-soft bg-surface px-2 py-0.5 rounded-full">{t("expired")}</span>;
  if (status === "success")
    return <span className="inline-flex text-xs font-medium text-success-strong bg-success-bg px-2 py-0.5 rounded-full">{t("success")}</span>;
  if (status === "failed")
    return <span className="inline-flex text-xs font-medium text-error-strong bg-error-bg px-2 py-0.5 rounded-full">{t("failed")}</span>;
  if (status === "running" || isGeneratingScripts)
    return <span className="inline-flex text-xs font-medium text-info-strong bg-info-bg px-2 py-0.5 rounded-full animate-pulse">{t("running")}</span>;
  if (status === "awaiting_user") {
    // Gefuellte Markenfarbe, weil das zarte Abzeichen in der Liste untergegangen ist.
    const cls = "inline-flex text-xs font-semibold text-on-accent bg-kb px-2 py-0.5 rounded-full";
    if (resumeHref)
      return <a href={resumeHref} onClick={onResume} className="btn-primary inline-flex text-xs font-semibold px-2 py-0.5 rounded-full">{t("awaitingUser")}</a>;
    return <span className={cls}>{t("awaitingUser")}</span>;
  }
  if (status === "queued")
    return <span className="inline-flex text-xs font-medium text-info-strong bg-info-bg px-2 py-0.5 rounded-full">{t("queued")}</span>;
  return <span className="inline-flex text-xs font-medium text-warn-strong bg-warn-bg px-2 py-0.5 rounded-full">{t("pending")}</span>;
}
