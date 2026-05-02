"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ChartBar } from "@phosphor-icons/react";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDate, formatDuration } from "@/lib/format";
import { JobStatusBadge } from "../_shared";

interface ToolStat {
  tool: string;
  label: string;
  total: number;
  success: number;
  failed: number;
  avg_seconds: number | null;
}

interface ActivityEntry {
  user: string;
  tool: string;
  tool_label: string;
  status: string;
  filename: string | null;
  created_at: string;
  duration_seconds: number | null;
}

interface StatsData {
  by_tool: ToolStat[];
  activity: ActivityEntry[];
  days: number;
}

export default function StatsTab() {
  const t = useTranslations("admin");
  const [data, setData] = useState<StatsData | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/admin/stats?days=${days}`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setData(d))
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) return <p className="text-sm text-muted">{t("loading")}</p>;
  if (!data) return <p className="text-sm text-error">{t("loadError")}</p>;

  const totalJobs = data.by_tool.reduce((s, x) => s + x.total, 0);
  const totalSuccess = data.by_tool.reduce((s, x) => s + x.success, 0);
  const totalFailed = data.by_tool.reduce((s, x) => s + x.failed, 0);

  const periodLabel = (d: number) =>
    d === 7 ? t("stats.days7") : d === 30 ? t("stats.month1") : d === 90 ? t("stats.months3") : t("stats.months6");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted">{t("stats.period")}</span>
        {[7, 30, 90, 180].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${days === d ? "bg-kb text-white border-kb" : "border-border text-foreground-soft hover:border-kb hover:text-kb"}`}
          >
            {periodLabel(d)}
          </button>
        ))}
      </div>

      {totalJobs === 0 ? (
        <EmptyState
          size="lg"
          icon={<ChartBar size={40} weight="bold" />}
          text={t("stats.empty")}
        />
      ) : (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-background border border-border-soft rounded-lg p-4">
            <p className="text-xs text-muted uppercase tracking-wide">{t("stats.total")}</p>
            <p className="text-2xl font-bold text-foreground mt-1">{totalJobs}</p>
          </div>
          <div className="bg-background border border-border-soft rounded-lg p-4">
            <p className="text-xs text-muted uppercase tracking-wide">{t("stats.successful")}</p>
            <p className="text-2xl font-bold text-success mt-1">{totalSuccess}</p>
          </div>
          <div className="bg-background border border-border-soft rounded-lg p-4">
            <p className="text-xs text-muted uppercase tracking-wide">{t("stats.failed")}</p>
            <p className="text-2xl font-bold text-error mt-1">{totalFailed}</p>
          </div>
        </div>
      )}

      {data.by_tool.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {data.by_tool.map((tool) => (
            <div key={tool.tool} className="bg-background border border-border-soft rounded-lg p-4">
              <p className="text-xs font-medium text-muted truncate">{tool.label}</p>
              <p className="text-xl font-bold text-foreground mt-1">{tool.total}</p>
              <div className="flex items-center gap-3 mt-2 text-xs">
                <span className="text-success">{t("stats.ok", { n: tool.success })}</span>
                {tool.failed > 0 && <span className="text-error">{t("stats.fail", { n: tool.failed })}</span>}
              </div>
              <p className="text-[10px] text-muted-soft mt-1">
                {tool.avg_seconds != null ? t("stats.avgPrefix", { duration: formatDuration(tool.avg_seconds) }) : ""}
              </p>
            </div>
          ))}
        </div>
      )}

      {data.activity.length > 0 && (
        <div className="bg-background border border-border-soft rounded-lg overflow-hidden">
          <h3 className="text-sm font-medium p-4 pb-2">{t("stats.lastActivity")}</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-soft text-left text-xs text-muted uppercase">
                  <th className="px-4 py-2">{t("stats.colUser")}</th>
                  <th className="px-4 py-2">{t("stats.colTool")}</th>
                  <th className="px-4 py-2">{t("stats.colStatus")}</th>
                  <th className="px-4 py-2 text-right">{t("stats.colDuration")}</th>
                  <th className="px-4 py-2 text-right">{t("stats.colDate")}</th>
                </tr>
              </thead>
              <tbody>
                {data.activity.map((a, i) => (
                  <tr key={i} className="border-b border-border-soft hover:bg-surface">
                    <td className="px-4 py-2 text-foreground-soft">{a.user}</td>
                    <td className="px-4 py-2 text-foreground-soft">{a.tool_label}</td>
                    <td className="px-4 py-2">
                      <JobStatusBadge status={a.status} />
                    </td>
                    <td className="px-4 py-2 text-right text-muted">
                      {formatDuration(a.duration_seconds)}
                    </td>
                    <td className="px-4 py-2 text-right text-muted-soft whitespace-nowrap">
                      {formatDate(a.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
