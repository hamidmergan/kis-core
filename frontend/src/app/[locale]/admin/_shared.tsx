"use client";

import { useTranslations } from "next-intl";

export interface PendingUser {
  id: number;
  ldap_username: string;
  display_name: string;
  email: string | null;
  created_at: string;
}

export interface AdminUser {
  id: number;
  ldap_username: string;
  display_name: string;
  email: string | null;
  active: number;
  created_at: string;
  role?: "admin" | "staff" | "user" | "custom";
  custom_role_id?: number | null;
}

export interface AdminJob {
  job_uuid: string;
  tool: string;
  tool_label: string;
  original_filename: string;
  status: string;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  user_display_name: string;
}

export function JobStatusBadge({ status }: { status: string }) {
  const t = useTranslations("admin.jobStatus");
  if (status === "success")
    return <span className="text-xs font-medium text-success-strong bg-success-bg px-2 py-0.5 rounded-full">{t("success")}</span>;
  if (status === "failed")
    return <span className="text-xs font-medium text-error-strong bg-error-bg px-2 py-0.5 rounded-full">{t("failed")}</span>;
  if (status === "running")
    return <span className="text-xs font-medium text-info-strong bg-info-bg px-2 py-0.5 rounded-full animate-pulse">{t("running")}</span>;
  if (status === "queued")
    return <span className="text-xs font-medium text-info-strong bg-info-bg px-2 py-0.5 rounded-full">{t("queued")}</span>;
  return <span className="text-xs font-medium text-warn-strong bg-warn-bg px-2 py-0.5 rounded-full">{t("pending")}</span>;
}
