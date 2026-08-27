import { useTranslations } from "next-intl";
import StatusMark from "@/components/ui/StatusMark";
import { jobStatusDisplay } from "@/lib/jobStatusDisplay";
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
  const anzeige = jobStatusDisplay(status, { expired, isGeneratingScripts });

  // Resuming is an action, not a state, and therefore gets a button.
  if (anzeige.kind === "action") {
    if (resumeHref)
      return (
        <a
          href={resumeHref}
          onClick={onResume}
          className="btn-primary inline-flex text-xs font-medium px-2.5 py-1 rounded-md"
        >
          {t("awaitingUser")}
        </a>
      );
    return <StatusMark tone="brand" className="text-xs">{t("awaitingUser")}</StatusMark>;
  }

  return (
    <StatusMark tone={anzeige.tone} pulse={anzeige.pulse} className="text-xs">
      {t(anzeige.key as "expired" | "success" | "failed" | "running" | "queued" | "pending")}
    </StatusMark>
  );
}
