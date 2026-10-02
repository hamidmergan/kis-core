"use client";

import { useEffect, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { loadEventConfig, useEventAdminState } from "@/lib/event/adminStore";

/** Loads the event settings once and renders the tab only when they are there, a status line shows the saving. */
export default function EventAdminGate({ children }: { children: ReactNode }) {
  const t = useTranslations("eventAdmin");
  const { config, loadFailed, status, error } = useEventAdminState();
  useEffect(() => loadEventConfig(), []);
  if (loadFailed) return <p className="text-sm text-error">{t("loadFailed")}</p>;
  if (!config) return <p className="text-sm text-muted">{t("loading")}</p>;
  return (
    <div className="flex flex-col gap-4">
      <p className={`text-xs h-4 ${status === "failed" ? "text-error" : "text-muted"}`} role="status" data-testid="event-save-status">
        {status === "saving" && t("saving")}
        {status === "saved" && t("saved")}
        {status === "failed" && (error ?? t("saveFailed"))}
      </p>
      {children}
    </div>
  );
}
