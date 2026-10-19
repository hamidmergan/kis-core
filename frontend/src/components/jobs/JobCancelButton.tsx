"use client";

import { useTranslations } from "next-intl";
import { X } from "@phosphor-icons/react";
import { notifyJobsChanged } from "@/lib/jobs-events";

/** Stops a running job on the server, the job list updates right after. */
export function cancelJob(uuid: string | null | undefined) {
  if (!uuid) return;
  fetch(`/api/jobs/${uuid}`, { method: "DELETE", credentials: "include" }).catch(() => {});
  notifyJobsChanged();
}

/** The cancel button next to the submit button while a job runs. */
export default function JobCancelButton({ onClick }: { onClick: () => void }) {
  const t = useTranslations("common");
  return (
    <button
      type="button"
      onClick={onClick}
      className="self-start btn-cancel px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors flex items-center gap-2"
    >
      <X size={16} weight="bold" />
      {t("cancelJob")}
    </button>
  );
}
