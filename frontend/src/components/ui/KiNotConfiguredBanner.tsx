"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Warning } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";

type Props = {
  /** Feature ids whose configuration is required for the surrounding tool. */
  features: string[];
  /** Whether the current user is an admin (controls whether to show a config link). */
  isAdmin?: boolean;
  className?: string;
};

export type FeatureStatus = Record<string, boolean>;

export async function fetchFeatureStatus(features: string[]): Promise<FeatureStatus> {
  const qs = features.length ? `?features=${features.join(",")}` : "";
  const res = await fetch(`/api/ki/feature-status${qs}`, { credentials: "include" });
  if (!res.ok) return {};
  const data = (await res.json()) as { status: FeatureStatus };
  return data.status ?? {};
}

/**
 * Renders a one-line warning banner when any of the required ``features`` is
 * not configured. Falls back to ``null`` (no DOM) when everything is fine, so
 * callers can safely place this above any tool and pay nothing at runtime once
 * the admin has set things up.
 */
export default function KiNotConfiguredBanner({ features, isAdmin = false, className }: Props) {
  const t = useTranslations("ki.notConfigured");
  const [missing, setMissing] = useState<string[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchFeatureStatus(features).then((status) => {
      if (cancelled) return;
      const m = features.filter((f) => status[f] === false);
      setMissing(m);
    });
    return () => {
      cancelled = true;
    };
  }, [features]);

  if (missing === null || missing.length === 0) return null;

  return (
    <div
      role="alert"
      className={`flex items-start gap-2 bg-warn-bg border border-warn-border rounded-md px-3 py-2 text-sm text-warn-strong ${className ?? ""}`}
    >
      <Warning size={16} weight="bold" className="mt-0.5 shrink-0" />
      <div className="flex-1">
        <p className="font-medium">{t("title")}</p>
        <p className="text-xs mt-0.5">
          {t("missing", {
            features: missing.map((f) => t(`featureName.${f}`)).join(", "),
          })}
        </p>
        {isAdmin && (
          <Link
            href="/admin?tab=ki"
            className="inline-block mt-1 text-xs font-medium underline hover:no-underline"
          >
            {t("configureLink")}
          </Link>
        )}
      </div>
    </div>
  );
}
