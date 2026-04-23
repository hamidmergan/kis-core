"use client";

import { useEffect, useState } from "react";
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

  if (loading) return <p className="text-sm text-gray-500">Laden…</p>;
  if (!data) return <p className="text-sm text-red-500">Fehler beim Laden</p>;

  const totalJobs = data.by_tool.reduce((s, t) => s + t.total, 0);
  const totalSuccess = data.by_tool.reduce((s, t) => s + t.success, 0);
  const totalFailed = data.by_tool.reduce((s, t) => s + t.failed, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">Zeitraum:</span>
        {[7, 30, 90, 180].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${days === d ? "bg-primary text-white border-primary" : "border-gray-300 text-gray-600 hover:border-gray-400"}`}
          >
            {d === 7 ? "7 Tage" : d === 30 ? "1 Monat" : d === 90 ? "3 Monate" : "6 Monate"}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Gesamt</p>
          <p className="text-2xl font-bold text-gray-800 mt-1">{totalJobs}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Erfolgreich</p>
          <p className="text-2xl font-bold text-green-600 mt-1">{totalSuccess}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Fehlgeschlagen</p>
          <p className="text-2xl font-bold text-red-600 mt-1">{totalFailed}</p>
        </div>
      </div>

      {data.by_tool.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {data.by_tool.map((t) => (
            <div key={t.tool} className="bg-white border border-gray-200 rounded-lg p-4">
              <p className="text-xs font-medium text-gray-500 truncate">{t.label}</p>
              <p className="text-xl font-bold text-gray-800 mt-1">{t.total}</p>
              <div className="flex items-center gap-3 mt-2 text-xs">
                <span className="text-green-600">{t.success} ok</span>
                {t.failed > 0 && <span className="text-red-600">{t.failed} fehl</span>}
              </div>
              <p className="text-[10px] text-gray-400 mt-1">
                {t.avg_seconds != null ? `Ø ${formatDuration(t.avg_seconds)}` : ""}
              </p>
            </div>
          ))}
        </div>
      )}

      {data.activity.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <h3 className="text-sm font-medium p-4 pb-2">Letzte Aktivität</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs text-gray-500 uppercase">
                  <th className="px-4 py-2">User</th>
                  <th className="px-4 py-2">Tool</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2 text-right">Dauer</th>
                  <th className="px-4 py-2 text-right">Datum</th>
                </tr>
              </thead>
              <tbody>
                {data.activity.map((a, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-4 py-2 text-gray-700">{a.user}</td>
                    <td className="px-4 py-2 text-gray-600">{a.tool_label}</td>
                    <td className="px-4 py-2">
                      <JobStatusBadge status={a.status} />
                    </td>
                    <td className="px-4 py-2 text-right text-gray-500">
                      {formatDuration(a.duration_seconds)}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-400 whitespace-nowrap">
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
